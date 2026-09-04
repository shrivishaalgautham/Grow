import httpx
import pytest
import respx

from app.api.symbols import CATALYSTS_PER_MINUTE
from app.providers.ratelimit import TokenBucket
from tests.api.support import EVENT_SYMBOL, start_session
from tests.providers.conftest import load_json, load_text

QUIET_SYMBOL = "RELIANCE.NS"


@pytest.fixture(autouse=True)
def bypass_bucket(monkeypatch):
    monkeypatch.setattr(TokenBucket, "acquire", lambda self, timeout_s=10.0: None)


@pytest.fixture
def router():
    with respx.mock(assert_all_called=False) as mocked:
        yield mocked


def mock_feeds(router: respx.MockRouter) -> None:
    router.get(host="feeds.finance.yahoo.com", path="/rss/2.0/headline").mock(
        return_value=httpx.Response(200, text=load_text("yahoo_rss.xml"))
    )
    router.get(host="www.nseindia.com", path="/").mock(return_value=httpx.Response(200, text=""))
    router.get(host="www.nseindia.com", path="/api/corporate-announcements").mock(
        return_value=httpx.Response(200, json=load_json("nse_announcements.json"))
    )


def test_quiet_symbol_is_not_surfaced_and_no_upstream_call_is_made(client, seeded, router):
    mock_feeds(router)
    headers, _ = start_session(client, start_with_sample=True)

    response = client.get(f"/api/symbols/{QUIET_SYMBOL}/catalysts", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_surfaced"
    assert router.calls.call_count == 0


def test_symbol_outside_the_watchlist_is_not_surfaced(client, seeded, router):
    headers, _ = start_session(client)

    response = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_surfaced"


def test_changed_symbol_returns_pending_then_the_cached_result_with_one_upstream_fetch(
    client, seeded, router
):
    mock_feeds(router)
    headers, _ = start_session(client, start_with_sample=True)

    first = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers).json()
    second = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers).json()
    third = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers).json()

    assert first["status"] == "pending"
    assert second["status"] == "found"
    assert second["items"][0]["headline"] == "Reliance Retail files draft papers for IPO"
    assert {item["source"] for item in second["items"]} == {"yahoo_rss", "nse"}
    assert all("evil.example" not in item["headline"] for item in second["items"])
    assert third == second
    assert router.calls.call_count == 3


def test_unreachable_feeds_are_reported_as_unavailable(client, seeded, router):
    router.get(host="feeds.finance.yahoo.com").mock(return_value=httpx.Response(404))
    router.get(host="www.nseindia.com").mock(return_value=httpx.Response(403))
    headers, _ = start_session(client, start_with_sample=True)

    client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers)
    body = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers).json()

    assert body["status"] == "unavailable"
    assert body["items"] == []


def test_digest_reflects_the_cached_catalyst_status(client, seeded, router):
    mock_feeds(router)
    headers, _ = start_session(client, start_with_sample=True)
    client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers)

    digest = client.get("/api/watchlist/digest", headers=headers).json()

    statuses = {item["symbol"]: item["catalyst_status"] for item in digest["items"]}
    assert statuses[EVENT_SYMBOL] == "found"
    assert statuses[QUIET_SYMBOL] == "not_fetched"


def test_catalyst_requests_beyond_the_per_minute_budget_are_rate_limited(client, seeded, router):
    mock_feeds(router)
    headers, _ = start_session(client, start_with_sample=True)
    for _ in range(CATALYSTS_PER_MINUTE):
        response = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers)
        assert response.status_code == 200

    response = client.get(f"/api/symbols/{EVENT_SYMBOL}/catalysts", headers=headers)

    assert response.status_code == 429
