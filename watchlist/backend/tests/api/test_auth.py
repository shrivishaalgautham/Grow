import hashlib
from datetime import timedelta

from app import clock
from app.models import AuthSession
from tests.api.support import start_session

FROZEN_EPOCH = 1_800_000_000.0


def test_same_display_name_creates_two_distinct_users(client, seeded):
    _, first = start_session(client, display_name="demo")
    _, second = start_session(client, display_name="demo")

    assert first["user"]["display_name"] == "demo"
    assert first["user"]["id"] != second["user"]["id"]


def test_missing_token_is_unauthorized(client, seeded):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_garbage_token_is_unauthorized(client, seeded):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_expired_token_reports_session_expired(client, db, seeded):
    headers, body = start_session(client)
    token = body["token"]
    auth = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
    auth.expires_at = clock.now() - timedelta(seconds=1)
    db.commit()

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_deleting_the_session_removes_the_user(client, seeded):
    headers, _ = start_session(client, display_name="temp-user")

    assert client.delete("/api/auth/session", headers=headers).status_code == 204
    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_eleventh_session_from_one_ip_in_an_hour_is_rate_limited(client, seeded, monkeypatch):
    monkeypatch.setattr("app.deps.time.time", lambda: FROZEN_EPOCH)
    for _ in range(10):
        start_session(client)

    response = client.post("/api/auth/session", json={})

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "rate_limited"
    assert error["retry_after_seconds"] >= 1
