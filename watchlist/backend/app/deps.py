import hashlib
import logging
import re
import time
from collections.abc import Callable
from typing import Literal

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app import clock
from app.cache import cache
from app.db import get_session
from app.models import AuthSession, Symbol, User
from app.schemas import SYMBOL_PATTERN

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, retry_after_seconds: int | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after_seconds = retry_after_seconds


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "unauthorized", "missing bearer token")
    auth = session.get(AuthSession, hashlib.sha256(token.strip().encode()).hexdigest())
    if auth is None:
        raise ApiError(401, "unauthorized", "unknown session")
    if auth.expires_at < clock.now():
        raise ApiError(401, "session_expired", "session expired")
    return auth.user


def valid_symbol(symbol: str, session: Session = Depends(get_session)) -> Symbol:
    if not re.fullmatch(SYMBOL_PATTERN, symbol):
        raise ApiError(404, "invalid_symbol", "unknown symbol")
    row = session.get(Symbol, symbol)
    if row is None or not row.is_active:
        raise ApiError(404, "invalid_symbol", "unknown symbol")
    return row


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_window(scope: str, limit: int, window_seconds: int, ident: str) -> None:
    now = int(time.time())
    window_start = now - now % window_seconds
    count = cache.incr(f"rl:{scope}:{ident}:{window_start}", window_seconds)
    if count <= limit:
        return
    ident_hash = hashlib.sha256(ident.encode()).hexdigest()[:12]
    log.info("rate_limited scope=%s ident=%s count=%d", scope, ident_hash, count)
    raise ApiError(
        429,
        "rate_limited",
        "too many requests",
        retry_after_seconds=max(1, window_start + window_seconds - now),
    )


def rate_limit(
    scope: str, limit: int, window_seconds: int, per: Literal["ip", "user"] = "ip"
) -> Callable[..., None]:
    if per == "user":

        def by_user(user: User = Depends(current_user)) -> None:
            enforce_window(scope, limit, window_seconds, str(user.id))

        return by_user

    def by_ip(request: Request) -> None:
        enforce_window(scope, limit, window_seconds, client_ip(request))

    return by_ip
