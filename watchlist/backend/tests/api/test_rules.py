from tests.api.support import EVENT_SYMBOL, start_session

ALWAYS_TRUE_FOR_ADANI = {
    "nl_text": "alert me on any adani volume",
    "rule": {"symbols": [EVENT_SYMBOL], "all": [{"field": "rvol", "op": ">=", "value": 0}]},
}


def test_rules_are_created_listed_with_todays_matches_and_deleted(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)

    created = client.post("/api/rules", json=ALWAYS_TRUE_FOR_ADANI, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["rule"] == ALWAYS_TRUE_FOR_ADANI["rule"]
    assert body["preview"] == "Alert on ADANIENT when its relative volume is at least 0×."
    assert body["enabled"] is True

    listed = client.get("/api/rules", headers=headers).json()
    assert [r["id"] for r in listed] == [body["id"]]
    assert listed[0]["matched_today"] == [EVENT_SYMBOL]
    assert listed[0]["preview"] == body["preview"]

    digest = client.get("/api/watchlist/digest", headers=headers).json()
    adani = next(item for item in digest["items"] if item["symbol"] == EVENT_SYMBOL)
    assert [s["rule_id"] for s in adani["signals"] if s["type"] == "USER_RULE"] == [body["id"]]

    assert client.delete(f"/api/rules/{body['id']}", headers=headers).status_code == 204
    assert client.get("/api/rules", headers=headers).json() == []


def test_rules_are_scoped_to_their_owner(client, seeded):
    alice, _ = start_session(client, start_with_sample=True)
    bob, _ = start_session(client, start_with_sample=True)
    rule_id = client.post("/api/rules", json=ALWAYS_TRUE_FOR_ADANI, headers=alice).json()["id"]

    assert client.get("/api/rules", headers=bob).json() == []
    assert client.delete(f"/api/rules/{rule_id}", headers=bob).status_code == 204
    assert [r["id"] for r in client.get("/api/rules", headers=alice).json()] == [rule_id]


def test_malformed_rule_id_is_rejected_without_leaking(client, seeded):
    headers, _ = start_session(client)

    response = client.delete("/api/rules/not-a-uuid", headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_rule"
