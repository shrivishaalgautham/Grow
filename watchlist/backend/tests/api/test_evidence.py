from app.cache import cache
from tests.api.support import start_session


def test_evidence_replays_the_callers_watchlist(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)

    response = client.get("/api/evidence/noise-reduction", headers=headers)

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["days"] == 90
    assert body["symbols_count"] == 12
    assert (
        body["suppressed"]["total"] == body["naive_pct_2"]["alerts"] - sum(1 for row in [] if row)
        or body["suppressed"]["total"] <= body["naive_pct_2"]["alerts"]
    )
    assert body["from_date"] < body["to_date"]
    assert set(body["suppressed"]) == {"total", "market_wide", "below_floor", "within_noise"}
    buckets = body["suppressed"]
    assert (
        buckets["market_wide"] + buckets["below_floor"] + buckets["within_noise"]
        == buckets["total"]
    )


def test_evidence_is_cached_per_watchlist_and_bar_date(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    client.get("/api/evidence/noise-reduction", headers=headers)
    cached_keys = [key for key in cache._memory if key.startswith("evidence:")]
    assert len(cached_keys) == 1

    client.get("/api/evidence/noise-reduction", headers=headers)

    assert [key for key in cache._memory if key.startswith("evidence:")] == cached_keys


def test_days_outside_the_bounds_are_rejected(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)

    assert client.get("/api/evidence/noise-reduction?days=5", headers=headers).status_code == 422
