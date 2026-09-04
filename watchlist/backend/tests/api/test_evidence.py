from tests.api.support import start_session

DAYS = 20


def test_noise_reduction_reports_the_three_baselines_and_caches(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/evidence/noise-reduction", params={"days": DAYS}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "days",
        "symbols_count",
        "from_date",
        "to_date",
        "computed_at",
        "naive_pct_2",
        "raw_z_2",
        "engine",
        "suppressed",
        "caught_extra",
    }
    assert body["days"] == DAYS
    assert body["symbols_count"] == 12
    assert body["from_date"] < body["to_date"]
    assert body["to_date"] == seeded.isoformat()
    assert body["suppressed"]["total"] <= body["naive_pct_2"]["alerts"]
    assert set(body["suppressed"]) == {"total", "market_wide", "below_floor", "unconfirmed_volume"}

    again = client.get("/api/evidence/noise-reduction", params={"days": DAYS}, headers=headers)
    assert again.json() == body


def test_days_outside_the_supported_window_are_rejected(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/evidence/noise-reduction", params={"days": 5}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_evidence_requires_a_session(client, seeded):
    assert client.get("/api/evidence/noise-reduction").status_code == 401
