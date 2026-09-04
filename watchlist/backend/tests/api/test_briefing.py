import json

from app.ai import briefing
from app.ai.client import Completion
from tests.api.support import start_session


def test_briefing_is_a_template_without_a_model_and_is_cached_afterwards(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)

    first = client.get("/api/watchlist/briefing", headers=headers).json()
    second = client.get("/api/watchlist/briefing", headers=headers).json()

    assert first["source"] == "template"
    assert first["was_cached"] is False
    assert "ADANIENT" in first["text"]
    assert len(first["text"]) <= 600
    assert second["text"] == first["text"]
    assert second["was_cached"] is True


def test_model_output_with_a_foreign_number_is_replaced_by_the_template(
    client, seeded, monkeypatch
):
    monkeypatch.setattr(briefing.client, "is_configured", lambda: True)
    monkeypatch.setattr(
        briefing.client,
        "complete",
        lambda *args: Completion("ADANIENT dropped 12.5% while peers were flat.", "m"),
    )
    headers, _ = start_session(client, start_with_sample=True)

    body = client.get("/api/watchlist/briefing", headers=headers).json()

    assert body["source"] == "template"


def grounded_completion(purpose, system, user, max_tokens) -> Completion:
    facts = json.loads(user)
    top = facts["items"][0]
    return Completion(
        f"You were away {facts['away_human']}. {top['symbol']} moved {top['residual_pct']}% "
        f"against a peer group at {top['peer_change_pct']}%, and no public catalyst was found.",
        "m",
    )


def test_grounded_model_output_is_served_as_llm(client, seeded, monkeypatch):
    monkeypatch.setattr(briefing.client, "is_configured", lambda: True)
    monkeypatch.setattr(briefing.client, "complete", grounded_completion)
    headers, _ = start_session(client, start_with_sample=True)

    body = client.get("/api/watchlist/briefing", headers=headers).json()

    assert body["source"] == "llm"
    assert body["text"].startswith("You were away ")
    assert "ADANIENT" in body["text"]


def test_marking_all_reviewed_changes_the_briefing_cache_key(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    before = client.get("/api/watchlist/briefing", headers=headers).json()
    client.post("/api/watchlist/seen", json={"symbols": "all"}, headers=headers)

    after = client.get("/api/watchlist/briefing", headers=headers).json()

    assert after["was_cached"] is False
    assert after["text"] != before["text"]
    assert "Nothing among your 12 stocks needed attention" in after["text"]
