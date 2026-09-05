import base64
import hashlib
import json
import logging
import re
import secrets

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.api.auth import issue_session
from app.api.ratelimit import global_ip_limit
from app.cache import cache
from app.config import settings
from app.db import get_session
from app.deps import ApiError, rate_limit
from app.models import User

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
JWKS_CACHE_KEY = "oauth:google:jwks"
JWKS_TTL_S = 3600
STATE_TTL_S = 600
NAME_SLUG_RE = re.compile(r"[^a-z0-9_-]+")

_http = httpx.Client(timeout=10.0)

router = APIRouter(prefix="/auth/google", tags=["auth"], dependencies=[Depends(global_ip_limit)])


@router.get("/start", dependencies=[Depends(rate_limit("oauth_start", 10, 3600, per="ip"))])
def start() -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = _code_challenge(verifier)
    cache.set_many({f"oauth:state:{state}": verifier}, ttl=STATE_TTL_S)
    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{AUTHORIZE_URL}?{httpx.QueryParams(params)}")


@router.get("/callback", dependencies=[Depends(rate_limit("oauth_callback", 20, 3600, per="ip"))])
def callback(code: str, state: str, session: Session = Depends(get_session)) -> RedirectResponse:
    verifier = cache.get(f"oauth:state:{state}")
    if verifier is None:
        raise ApiError(400, "invalid_oauth_state", "sign-in link expired, try again")
    cache.delete(f"oauth:state:{state}")
    claims = _exchange_and_verify(code, verifier)
    user = _find_or_create_user(session, claims)
    now = clock.now()
    token, _ = issue_session(session, user, now)
    session.commit()
    return RedirectResponse(f"{settings.app_base_url}/?t={token}")


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _exchange_and_verify(code: str, verifier: str) -> dict:
    response = _http.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
            "redirect_uri": settings.oidc_redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
    )
    if response.status_code != 200:
        log.warning("oauth_token_exchange_failed status=%d", response.status_code)
        raise ApiError(401, "oauth_failed", "google sign-in failed")
    id_token = response.json().get("id_token")
    if not id_token:
        raise ApiError(401, "oauth_failed", "google sign-in failed")
    return _verify_id_token(id_token)


def _verify_id_token(id_token: str) -> dict:
    keyset = _jwks()
    try:
        token = jwt.decode(id_token, keyset, algorithms=["RS256"])
    except JoseError as exc:
        log.warning("oauth_id_token_invalid reason=%s", type(exc).__name__)
        raise ApiError(401, "oauth_failed", "google sign-in failed") from exc
    registry = jwt.JWTClaimsRegistry(
        now=lambda: int(clock.now().timestamp()),
        leeway=30,
        iss={"essential": True, "values": [settings.oidc_issuer, "accounts.google.com"]},
        aud={"essential": True, "value": settings.oidc_client_id},
        exp={"essential": True},
        sub={"essential": True},
    )
    try:
        registry.validate(token.claims)
    except JoseError as exc:
        log.warning("oauth_id_token_claims_invalid reason=%s", type(exc).__name__)
        raise ApiError(401, "oauth_failed", "google sign-in failed") from exc
    return token.claims


def _jwks() -> KeySet:
    raw = cache.get(JWKS_CACHE_KEY)
    if raw is None:
        response = _http.get(JWKS_URL)
        response.raise_for_status()
        raw = response.text
        cache.set_many({JWKS_CACHE_KEY: raw}, ttl=JWKS_TTL_S)
    return KeySet.import_key_set(json.loads(raw))


def _find_or_create_user(session: Session, claims: dict) -> User:
    sub = claims["sub"]
    email = claims.get("email")
    user = session.scalar(select(User).where(User.google_sub == sub))
    if user is not None:
        if email and user.email != email:
            user.email = email
        return user
    user = User(display_name=_display_name_from(email, sub), email=email, google_sub=sub)
    session.add(user)
    session.flush()
    return user


def _display_name_from(email: str | None, sub: str) -> str:
    local = (email or "").split("@", 1)[0].lower()
    slug = NAME_SLUG_RE.sub("-", local).strip("-")
    if len(slug) < 3:
        slug = f"user-{sub[-8:]}"
    return slug[:32]
