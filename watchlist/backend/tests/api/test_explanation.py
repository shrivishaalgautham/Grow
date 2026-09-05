import httpx
import pytest
import respx

from app.ai import explain
from app.ai.client import Completion
from app.providers.ratelimit import TokenBucket
from tests.api.support import EVENT_SYMBOL, start_session
from tests.api.test_catalysts import QUIET_SYMBOL, mock_feeds


@pytest.fixture(autouse=True)
def bypass_bucket(monkeypatch):
    monkeypatch.setattr(TokenBucket, "acquire", lambda self, timeout_s=10.0: None)


@pytest.fixture
def router():
    with respx.mock(assert_all_called=False) as mocked:
        yield mocked


def test_quiet_symbol_is_not_explained(client, seeded, router):
    headers, _ = start_session(client, start_with_sample=True)

    response = client.get(f"/api/symbols/{QUIET_SYMBOL}/explanation", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_surfaced"


def test_explanation_is_pending_until_catalysts_arrive_then_grounded_by_template(
    client, seeded, router
):
    mock_feeds(router)
    headers, _ = start_session(client, start_with_sample=True)

    first = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()
    second = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()
    third = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()

    assert first["status"] == "pending"
    assert second["status"] == "ready"
    assert second["source"] == "template"
    assert second["catalyst_status"] == "found"
    assert second["text"].startswith("ADANIENT moved ")
    assert "coincided with" in second["text"]
    assert "Reliance Retail files draft papers for IPO" in second["text"]
    assert len(second["items"]) <= 3
    assert third["was_cached"] is True
    assert third["text"] == second["text"]


def test_model_output_with_a_foreign_number_falls_back_to_the_template(
    client, seeded, router, monkeypatch
):
    mock_feeds(router)
    monkeypatch.setattr(explain.client, "is_configured", lambda: True)
    monkeypatch.setattr(
        explain.client, "complete", lambda *args: Completion("ADANIENT jumped 42.0% today.", "m")
    )
    headers, _ = start_session(client, start_with_sample=True)
    client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers)

    body = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()

    assert body["source"] == "template"


def test_grounded_model_output_is_served(client, seeded, router, monkeypatch):
    mock_feeds(router)
    monkeypatch.setattr(explain.client, "is_configured", lambda: True)

    def grounded(purpose, system, user, max_tokens):
        import json

        item = json.loads(user)["items"][0]
        return Completion(
            f"{item['symbol']} moved {item['today_change_pct']}% against peers at "
            f"{item['peer_change_pct']}%, a {item['residual_pct']}% stock-specific move that "
            "coincided with a filing.",
            "m",
        )

    monkeypatch.setattr(explain.client, "complete", grounded)
    headers, _ = start_session(client, start_with_sample=True)
    client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers)

    body = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()

    assert body["source"] == "llm"
    assert body["text"].startswith("ADANIENT moved")


def test_unavailable_sources_are_said_so_in_the_template(client, seeded, router):
    router.get(host="feeds.finance.yahoo.com").mock(return_value=httpx.Response(404))
    router.get(host="www.nseindia.com").mock(return_value=httpx.Response(403))
    router.get(host="news.google.com").mock(return_value=httpx.Response(503))
    router.get(host="api.gdeltproject.org").mock(return_value=httpx.Response(503))
    headers, _ = start_session(client, start_with_sample=True)
    client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers)

    body = client.get(f"/api/symbols/{EVENT_SYMBOL}/explanation", headers=headers).json()

    assert body["catalyst_status"] == "unavailable"
    assert "could not be checked" in body["text"]
