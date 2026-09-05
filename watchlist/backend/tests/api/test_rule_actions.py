import pytest

from app import clock
from app.notify import email
from app.notify import rule_actions as rule_actions_job
from tests.api.support import NoCloseSession, start_session
from tests.api.test_notifications import subscribe_and_verify

ANY_VOLUME_RULE = {"symbols": "all", "all": [{"field": "rvol", "op": ">=", "value": 0.5}]}


@pytest.fixture(autouse=True)
def outbox():
    email.console_outbox.clear()
    yield email.console_outbox
    email.console_outbox.clear()


@pytest.fixture
def rule_actions_db(db, monkeypatch):
    monkeypatch.setattr(rule_actions_job.db, "SessionLocal", lambda: NoCloseSession(db))
    return db


def create_rule(client, headers, actions):
    response = client.post(
        "/api/rules",
        json={"nl_text": "any volume", "rule": ANY_VOLUME_RULE, "actions": actions},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_email_action_fires_once_for_a_matched_rule(client, seeded, outbox, rule_actions_db):
    headers, _ = start_session(client, start_with_sample=True)
    subscribe_and_verify(client, headers, outbox)
    outbox.clear()
    create_rule(client, headers, [{"type": "email"}])

    fired_first = rule_actions_job.run(clock.now())
    fired_second = rule_actions_job.run(clock.now())

    assert fired_first > 0
    assert fired_second == 0
    assert len(outbox) == fired_first
    assert all(message.subject.startswith("Rule matched:") for message in outbox)


def test_webhook_action_posts_a_signed_payload(client, seeded, rule_actions_db, monkeypatch):
    headers, _ = start_session(client, start_with_sample=True)
    calls = []
    monkeypatch.setattr(
        "app.notify.rule_actions.webhook.send",
        lambda url, secret, payload: calls.append((url, secret, payload)) or True,
    )
    rule = create_rule(client, headers, [{"type": "webhook", "url": "https://example.com/hook"}])
    secret = rule["actions"][0]["secret"]

    fired = rule_actions_job.run(clock.now())

    assert fired > 0
    assert len(calls) == fired
    url, sent_secret, payload = calls[0]
    assert url == "https://example.com/hook"
    assert sent_secret == secret
    assert payload["rule_id"] == rule["id"]
    assert "headline" in payload


def test_email_action_without_a_verified_channel_sends_nothing(
    client, seeded, outbox, rule_actions_db
):
    headers, _ = start_session(client, start_with_sample=True)
    create_rule(client, headers, [{"type": "email"}])

    fired = rule_actions_job.run(clock.now())

    assert fired > 0
    assert outbox == []
