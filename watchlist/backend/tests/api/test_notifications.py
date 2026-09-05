import re
from datetime import timedelta

import pytest

from app import clock
from app.notify import dispatch as dispatch_job
from app.notify import email
from tests.api.support import EVENT_SYMBOL, start_session

LINK = re.compile(r"\?verify=([A-Za-z0-9_-]+)")


@pytest.fixture(autouse=True)
def outbox():
    email.console_outbox.clear()
    yield email.console_outbox
    email.console_outbox.clear()


@pytest.fixture
def dispatch_db(db, monkeypatch):
    monkeypatch.setattr(dispatch_job.db, "SessionLocal", lambda: _NoClose(db))
    return db


class _NoClose:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


def subscribe_and_verify(client, headers, outbox, address="trader@example.com") -> str:
    response = client.post("/api/notifications/email", json={"email": address}, headers=headers)
    assert response.status_code == 202, response.text
    token = LINK.search(outbox[-1].text).group(1)
    verified = client.post("/api/notifications/email/verify", json={"token": token})
    assert verified.status_code == 200, verified.text
    return token


def test_subscribe_sends_a_verification_link_and_verify_flips_the_status(client, seeded, outbox):
    headers, _ = start_session(client, start_with_sample=True)

    pending = client.post(
        "/api/notifications/email", json={"email": "Trader@Example.com"}, headers=headers
    ).json()
    assert pending == {
        "address_masked": "t***@example.com",
        "status": "pending",
        "verify_expires_at": pending["verify_expires_at"],
        "last_notified_at": None,
    }
    assert outbox[-1].to == "trader@example.com"
    assert "/?verify=" in outbox[-1].text

    subscribe_and_verify(client, headers, outbox)

    assert client.get("/api/notifications", headers=headers).json()["email"]["status"] == "verified"


def test_verify_rejects_unknown_and_reused_tokens(client, seeded, outbox):
    headers, _ = start_session(client, start_with_sample=True)
    token = subscribe_and_verify(client, headers, outbox)

    reused = client.post("/api/notifications/email/verify", json={"token": token})
    unknown = client.post("/api/notifications/email/verify", json={"token": "x" * 32})

    assert reused.status_code == 400
    assert unknown.status_code == 400


def test_invalid_addresses_are_rejected_at_the_boundary(client, seeded):
    headers, _ = start_session(client)

    response = client.post(
        "/api/notifications/email", json={"email": "not-an-email"}, headers=headers
    )

    assert response.status_code == 422


def test_dispatch_batches_new_signals_into_one_email_and_never_repeats_them(
    client, seeded, outbox, dispatch_db
):
    headers, _ = start_session(client, start_with_sample=True)
    subscribe_and_verify(client, headers, outbox)
    outbox.clear()
    now = clock.now()

    first = dispatch_job.dispatch(now)
    again = dispatch_job.dispatch(now + timedelta(hours=1))

    assert first.sent == 1
    assert again.sent == 0
    assert len(outbox) == 1
    message = outbox[0]
    assert message.to == "trader@example.com"
    assert message.subject.startswith("Watchlist: ")
    assert EVENT_SYMBOL.split(".")[0] in message.text
    assert "Unusually large stock-specific move" in message.text
    assert "/api/notifications/unsubscribe?token=" in message.text
    assert "not advice" in message.text


def test_dispatch_respects_the_minimum_gap_between_emails(client, seeded, outbox, dispatch_db):
    headers, _ = start_session(client, start_with_sample=True)
    subscribe_and_verify(client, headers, outbox)
    now = clock.now()
    dispatch_job.dispatch(now)

    summary = dispatch_job.dispatch(now + timedelta(minutes=5))

    assert summary.skipped_gap == 1


def test_unsubscribe_link_disables_the_channel_without_a_session(
    client, seeded, outbox, dispatch_db
):
    headers, _ = start_session(client, start_with_sample=True)
    subscribe_and_verify(client, headers, outbox)
    dispatch_job.dispatch(clock.now())
    token = re.search(r"unsubscribe\?token=([A-Za-z0-9_-]+)", outbox[-1].text).group(1)

    page = client.get("/api/notifications/unsubscribe", params={"token": token})

    assert page.status_code == 200
    assert "switched off" in page.text
    assert client.get("/api/notifications", headers=headers).json()["email"]["status"] == "disabled"
    assert dispatch_job.dispatch(clock.now() + timedelta(hours=2)).channels == 0


def test_channels_are_scoped_to_their_owner(client, seeded, outbox):
    alice, _ = start_session(client, display_name="alice")
    bob, _ = start_session(client, display_name="bob")
    subscribe_and_verify(client, alice, outbox, "alice@example.com")

    assert client.get("/api/notifications", headers=bob).json() == {"email": None}
    assert client.delete("/api/notifications/email", headers=bob).status_code == 204
    assert client.get("/api/notifications", headers=alice).json()["email"]["status"] == "verified"
    assert client.delete("/api/notifications/email", headers=alice).status_code == 204
    assert client.get("/api/notifications", headers=alice).json() == {"email": None}
