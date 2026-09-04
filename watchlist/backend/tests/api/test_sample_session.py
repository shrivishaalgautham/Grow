from datetime import datetime, timedelta

from tests.api.support import EVENT_HEADLINE, EVENT_SYMBOL, start_session


def test_sample_session_starts_with_a_populated_backdated_digest(client, seeded):
    latest_bar_date = seeded
    headers, body = start_session(client, start_with_sample=True)

    assert body["user"]["is_sample"] is True
    assert body["user"]["display_name"].startswith("sample-")
    me = client.get("/api/auth/me", headers=headers).json()
    reviewed_at = datetime.fromisoformat(me["last_reviewed_at"])
    assert reviewed_at.date() == latest_bar_date - timedelta(days=7)

    digest = client.get("/api/watchlist/digest", headers=headers).json()
    assert digest["total_count"] == 12
    assert digest["changed_count"] >= 1
    assert digest["items"][0]["symbol"] == EVENT_SYMBOL
    assert digest["items"][0]["is_changed"] is True
    assert digest["items"][0]["signals"][0]["headline"] == EVENT_HEADLINE
    assert digest["away_duration_seconds"] > 7 * 86400
