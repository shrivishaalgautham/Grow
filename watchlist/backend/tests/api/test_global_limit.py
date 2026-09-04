FROZEN_EPOCH = 1_800_000_000.0


def test_thirty_first_request_in_a_minute_is_rate_limited_but_health_is_exempt(
    client, seeded, monkeypatch
):
    monkeypatch.setattr("app.deps.time.time", lambda: FROZEN_EPOCH)
    for _ in range(30):
        assert client.get("/api/symbols/search", params={"q": "x"}).status_code == 401

    limited = client.get("/api/symbols/search", params={"q": "x"})

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.json()["error"]["retry_after_seconds"] >= 1
    assert client.get("/api/health").status_code == 200
