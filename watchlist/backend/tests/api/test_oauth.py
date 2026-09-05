import httpx
import respx
from joserfc import jwt
from joserfc.jwk import RSAKey

from app.api import oauth
from app.cache import cache
from app.config import settings
from app.models import User

KID = "test-kid"


def _signed_id_token(key: RSAKey, **claims) -> str:
    header = {"alg": "RS256", "kid": KID}
    payload = {
        "iss": "https://accounts.google.com",
        "aud": settings.oidc_client_id,
        "exp": 9_999_999_999,
        **claims,
    }
    return jwt.encode(header, payload, key)


def _mock_google(key: RSAKey, id_token: str) -> None:
    respx.post(oauth.TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"id_token": id_token})
    )
    jwks = {"keys": [key.as_dict(private=False)]}
    respx.get(oauth.JWKS_URL).mock(return_value=httpx.Response(200, json=jwks))


@respx.mock
def test_start_redirects_to_google_with_pkce_and_state(client, seeded):
    response = client.get("/api/auth/google/start", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert location.startswith(oauth.AUTHORIZE_URL)
    assert "code_challenge=" in location
    assert "state=" in location


@respx.mock
def test_callback_creates_a_user_from_google_claims(client, seeded, db):
    key = RSAKey.generate_key(2048, parameters={"kid": KID}, private=True)
    id_token = _signed_id_token(key, sub="google-sub-1", email="demo@example.com")
    _mock_google(key, id_token)
    cache.set_many({"oauth:state:abc": "verifier"}, ttl=60)

    response = client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "abc"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    assert response.headers["location"].startswith(f"{settings.app_base_url}/?t=")
    user = db.query(User).filter(User.google_sub == "google-sub-1").one()
    assert user.email == "demo@example.com"
    assert user.display_name == "demo"


@respx.mock
def test_callback_reuses_the_existing_user_on_second_sign_in(client, seeded, db):
    key = RSAKey.generate_key(2048, parameters={"kid": KID}, private=True)
    id_token = _signed_id_token(key, sub="google-sub-2", email="repeat@example.com")
    _mock_google(key, id_token)
    cache.set_many({"oauth:state:first": "verifier"}, ttl=60)
    client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "first"},
        follow_redirects=False,
    )
    first_count = db.query(User).filter(User.google_sub == "google-sub-2").count()

    cache.set_many({"oauth:state:second": "verifier"}, ttl=60)
    response = client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "second"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    assert db.query(User).filter(User.google_sub == "google-sub-2").count() == first_count == 1


@respx.mock
def test_callback_rejects_an_unknown_or_expired_state(client, seeded):
    response = client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "never-issued"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_oauth_state"


@respx.mock
def test_callback_rejects_a_token_signed_by_the_wrong_key(client, seeded):
    real_key = RSAKey.generate_key(2048, parameters={"kid": KID}, private=True)
    forged_key = RSAKey.generate_key(2048, parameters={"kid": KID}, private=True)
    id_token = _signed_id_token(forged_key, sub="google-sub-3", email="forged@example.com")
    _mock_google(real_key, id_token)
    cache.set_many({"oauth:state:forged": "verifier"}, ttl=60)

    response = client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "forged"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_failed"


@respx.mock
def test_callback_rejects_a_token_for_a_different_audience(client, seeded):
    key = RSAKey.generate_key(2048, parameters={"kid": KID}, private=True)
    header = {"alg": "RS256", "kid": KID}
    payload = {
        "iss": "https://accounts.google.com",
        "aud": "someone-elses-client-id",
        "exp": 9_999_999_999,
        "sub": "google-sub-4",
        "email": "wrong-aud@example.com",
    }
    id_token = jwt.encode(header, payload, key)
    _mock_google(key, id_token)
    cache.set_many({"oauth:state:wrong-aud": "verifier"}, ttl=60)

    response = client.get(
        "/api/auth/google/callback",
        params={"code": "auth-code", "state": "wrong-aud"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "oauth_failed"
