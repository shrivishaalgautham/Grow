from tests.api.support import start_session


def test_users_cannot_see_or_touch_each_others_watchlist(client, seeded):
    alice, _ = start_session(client, display_name="alice")
    bob, _ = start_session(client, display_name="bob")
    added = client.post("/api/watchlist/items", json={"symbol": "RELIANCE.NS"}, headers=alice)
    assert added.status_code == 201, added.text

    bobs_digest = client.get("/api/watchlist/digest", headers=bob).json()
    assert bobs_digest["total_count"] == 0
    assert bobs_digest["items"] == []

    bobs_seen = client.post("/api/watchlist/seen", json={"symbols": ["RELIANCE.NS"]}, headers=bob)
    assert bobs_seen.status_code == 400
    assert bobs_seen.json()["error"]["code"] == "not_in_watchlist"

    assert client.delete("/api/watchlist/items/RELIANCE.NS", headers=bob).status_code == 204
    alices_digest = client.get("/api/watchlist/digest", headers=alice).json()
    assert [item["symbol"] for item in alices_digest["items"]] == ["RELIANCE.NS"]
