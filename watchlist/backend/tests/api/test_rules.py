from app.api.ratelimit import LLM_HOURLY_PER_USER
from app.api.rules import MAX_RULES_PER_USER
from tests.api.support import start_session

RULE = {"symbols": ["RELIANCE.NS"], "all": [{"field": "rvol", "op": ">=", "value": 2}]}


def test_sixth_compile_in_an_hour_is_rate_limited(client, seeded):
    headers, _ = start_session(client)

    for _ in range(LLM_HOURLY_PER_USER):
        response = client.post("/api/rules/compile", json={"text": "3x volume"}, headers=headers)
        assert response.status_code == 200, response.text

    response = client.post("/api/rules/compile", json={"text": "3x volume"}, headers=headers)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.json()["error"]["retry_after_seconds"] >= 1


def test_compile_without_a_model_still_returns_a_readable_preview(client, seeded):
    headers, _ = start_session(client)

    response = client.post(
        "/api/rules/compile", json={"text": "reliance drops 2% on 3x volume"}, headers=headers
    )

    body = response.json()
    assert response.status_code == 200
    assert body["rule"]["symbols"] == ["RELIANCE.NS"]
    assert body["preview"].startswith("Alert on RELIANCE when")


def test_rules_are_scoped_to_their_owner(client, seeded):
    alice, _ = start_session(client, display_name="alice")
    bob, _ = start_session(client, display_name="bob")
    created = client.post(
        "/api/rules", json={"nl_text": "reliance 2x", "rule": RULE}, headers=alice
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]

    assert [r["id"] for r in client.get("/api/rules", headers=alice).json()] == [rule_id]
    assert client.get("/api/rules", headers=bob).json() == []
    assert client.delete(f"/api/rules/{rule_id}", headers=bob).status_code == 204
    assert [r["id"] for r in client.get("/api/rules", headers=alice).json()] == [rule_id]
    assert client.delete(f"/api/rules/{rule_id}", headers=alice).status_code == 204
    assert client.get("/api/rules", headers=alice).json() == []


def test_rule_with_a_symbol_outside_the_universe_is_rejected(client, seeded):
    headers, _ = start_session(client)
    rule = {**RULE, "symbols": ["ZOMATO.NS"]}

    response = client.post("/api/rules", json={"nl_text": "zomato", "rule": rule}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "not_in_universe"


def test_rule_bounds_are_enforced_at_the_api_boundary(client, seeded):
    headers, _ = start_session(client)
    rule = {"symbols": "all", "all": [{"field": "z_score", "op": ">=", "value": -1}]}

    response = client.post(
        "/api/rules", json={"nl_text": "anything", "rule": rule}, headers=headers
    )

    assert response.status_code == 422


def test_eleventh_rule_is_refused(client, seeded):
    headers, _ = start_session(client)
    for index in range(MAX_RULES_PER_USER):
        response = client.post(
            "/api/rules", json={"nl_text": f"rule {index}", "rule": RULE}, headers=headers
        )
        assert response.status_code == 201

    response = client.post(
        "/api/rules", json={"nl_text": "one more", "rule": RULE}, headers=headers
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_rule"


def test_matched_today_reports_symbols_the_rule_fires_on(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    rule = {"symbols": "all", "all": [{"field": "rvol", "op": ">=", "value": 0.5}]}
    client.post("/api/rules", json={"nl_text": "any volume", "rule": rule}, headers=headers)

    listed = client.get("/api/rules", headers=headers).json()

    assert len(listed) == 1
    assert len(listed[0]["matched_today"]) == 12
    digest = client.get("/api/watchlist/digest", headers=headers).json()
    assert all(
        any(s["type"] == "USER_RULE" and s["rule_id"] == listed[0]["id"] for s in item["signals"])
        for item in digest["items"]
    )


def test_email_action_is_stored_and_returned(client, seeded):
    headers, _ = start_session(client)

    created = client.post(
        "/api/rules",
        json={"nl_text": "reliance 2x", "rule": RULE, "actions": [{"type": "email"}]},
        headers=headers,
    )

    assert created.status_code == 201, created.text
    assert created.json()["actions"] == [{"type": "email"}]


def test_webhook_action_gets_a_server_generated_secret(client, seeded):
    headers, _ = start_session(client)

    created = client.post(
        "/api/rules",
        json={
            "nl_text": "reliance 2x",
            "rule": RULE,
            "actions": [{"type": "webhook", "url": "https://example.com/hooks/watchlist"}],
        },
        headers=headers,
    )

    assert created.status_code == 201, created.text
    action = created.json()["actions"][0]
    assert action["type"] == "webhook"
    assert action["url"] == "https://example.com/hooks/watchlist"
    assert len(action["secret"]) >= 32

    listed = client.get("/api/rules", headers=headers).json()
    assert listed[0]["actions"][0]["secret"] == action["secret"]


def test_webhook_action_pointed_at_localhost_is_rejected(client, seeded):
    headers, _ = start_session(client)

    response = client.post(
        "/api/rules",
        json={
            "nl_text": "reliance 2x",
            "rule": RULE,
            "actions": [{"type": "webhook", "url": "http://localhost:9000/hook"}],
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_webhook_action_pointed_at_a_private_ip_is_rejected(client, seeded):
    headers, _ = start_session(client)

    response = client.post(
        "/api/rules",
        json={
            "nl_text": "reliance 2x",
            "rule": RULE,
            "actions": [{"type": "webhook", "url": "http://192.168.1.5/hook"}],
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_client_supplied_webhook_secret_is_ignored(client, seeded):
    headers, _ = start_session(client)

    created = client.post(
        "/api/rules",
        json={
            "nl_text": "reliance 2x",
            "rule": RULE,
            "actions": [
                {"type": "webhook", "url": "https://example.com/hook", "secret": "attacker-chosen"}
            ],
        },
        headers=headers,
    )

    assert created.json()["actions"][0]["secret"] != "attacker-chosen"
