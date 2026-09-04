import json

import pytest
import respx

from app.config import settings
from tests.api.support import mock_llm, start_session

JSON_HEADERS = {"Content-Type": "application/json"}
ELEVEN_CONDITIONS = json.dumps([{"field": "rvol", "op": ">=", "value": 2}] * 11)


def condition(field: str, op: str, value) -> dict:
    return {"field": field, "op": op, "value": value}


def rule(symbols, *conditions) -> dict:
    return {"nl_text": "test rule", "rule": {"symbols": symbols, "all": list(conditions)}}


def post_rule(client, headers, payload) -> tuple[int, dict]:
    response = client.post(
        "/api/rules", content=json.dumps(payload), headers={**headers, **JSON_HEADERS}
    )
    return response.status_code, response.json()


@pytest.mark.parametrize(
    "payload",
    [
        rule(["ADANIENT.NS"], condition("rvol", ">=", float("nan"))),
        rule(["ADANIENT.NS"], condition("rvol", ">=", float("inf"))),
        rule(["ADANIENT.NS"], *[condition("rvol", ">=", 2)] * 11),
        rule(["ZZZZ.NS"], condition("rvol", ">=", 2)),
        rule("all", condition("z_score", ">=", -100)),
        rule("all", condition("z_score", ">=", 0), condition("rvol", ">=", 3)),
        rule([f"S{i}.NS" for i in range(21)], condition("rvol", ">=", 2)),
    ],
    ids=["nan", "infinity", "eleven_conditions", "unknown_symbol", "below_bounds", "vacuous", "21"],
)
def test_out_of_bounds_rules_are_rejected_as_invalid_rule(client, seeded, payload):
    headers, _ = start_session(client)

    status, body = post_rule(client, headers, payload)

    assert status == 400, body
    assert body["error"]["code"] == "invalid_rule"


def test_eleventh_rule_is_rejected(client, seeded):
    headers, _ = start_session(client)
    payload = rule(["ADANIENT.NS"], condition("rvol", ">=", 2))
    for _ in range(10):
        assert post_rule(client, headers, payload)[0] == 201

    status, body = post_rule(client, headers, payload)

    assert status == 400
    assert body["error"]["code"] == "invalid_rule"
    assert "10" in body["error"]["message"]


@respx.mock
@pytest.mark.parametrize(
    "llm_output",
    [
        "Sure! Here is prose without any JSON.",
        '{"error": "unsupported"}',
        '{"symbols": ["ADANIENT.NS"], "all": ' + ELEVEN_CONDITIONS + "}",
        '{"symbols": "all", "all": [{"field": "rvol", "op": ">=", "value": 0}]}',
        '{"symbols": ["ZZZZ.NS"], "all": [{"field": "rvol", "op": ">=", "value": 2}]}',
        '{"symbols": ["ADANIENT.NS"], "all": [{"field": "rsi", "op": ">=", "value": 70}]}',
    ],
)
def test_compile_never_fails_loudly_on_bad_model_output(client, seeded, monkeypatch, llm_output):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    headers, _ = start_session(client)
    mock_llm(llm_output)

    response = client.post("/api/rules/compile", json={"text": "alert me"}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rule"] is None
    assert body["preview"] is None
    assert body["error"] and len(body["error"]) <= 200


@respx.mock
def test_compile_returns_a_validated_rule_and_preview(client, seeded, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "sk-or-test")
    headers, _ = start_session(client)
    route = mock_llm(
        'Here you go: {"symbols": ["adanient"], "all": [{"field": "abs_residual_pct", '
        '"op": ">=", "value": 3}, {"field": "rvol", "op": ">=", "value": 2}]}'
    )

    response = client.post(
        "/api/rules/compile",
        json={"text": "tell me when Adani moves 3% on double volume"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["error"] is None
    assert body["rule"]["symbols"] == ["ADANIENT.NS"]
    assert body["preview"] == (
        "Alert on ADANIENT when its stock-specific move is at least 3%"
        " and its relative volume is at least 2×."
    )
    request = json.loads(route.calls.last.request.content)
    assert request["provider"] == {"data_collection": "deny"}
    assert (
        "<untrusted>tell me when Adani moves 3% on double volume</untrusted>"
        in (request["messages"][-1]["content"])
    )


def test_sixth_compile_in_an_hour_is_rate_limited(client, seeded):
    headers, _ = start_session(client)
    for _ in range(5):
        response = client.post("/api/rules/compile", json={"text": "alert me"}, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["rule"] is None

    limited = client.post("/api/rules/compile", json={"text": "alert me"}, headers=headers)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert limited.json()["error"]["retry_after_seconds"] >= 1


def test_compile_requires_a_session(client, seeded):
    response = client.post("/api/rules/compile", json={"text": "alert me"})

    assert response.status_code == 401
