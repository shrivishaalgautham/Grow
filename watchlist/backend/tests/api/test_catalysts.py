from datetime import date

import httpx
import pytest
import respx

from app import clock
from app.config import settings
from app.jobs.catalysts import claim_fetch
from app.providers.ratelimit import TokenBucket
from tests.api.support import EVENT_SYMBOL, start_session
from tests.providers.conftest import load_json, load_text

pytestmark = pytest.mark.usefixtures("bypass_bucket", "frozen_day")


@pytest.fixture
def bypass_bucket(monkeypatch):
    monkeypatch.setattr(TokenBucket, "acquire", lambda self, timeout_s=10.0: None)


@pytest.fixture
def frozen_day(monkeypatch):
    monkeypatch.setattr(settings, "replay_date", date(2026, 9, 4))


def rss_route() -> respx.Route:
    return respx.get(host="feeds.finance.yahoo.com", path="/rss/2.0/headline")


def nse_routes() -> respx.Route:
    respx.get("https://www.nseindia.com/").mock(return_value=httpx.Response(200, text=""))
    return respx.get(host="www.nseindia.com", path="/api/corporate-announcements")


def catalysts(client, headers, symbol=EVENT_SYMBOL):
    return client.get(f"/api/symbols/{symbol}/catalysts", headers=headers)


def test_quiet_symbol_is_not_surfaced(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    digest = client.get("/api/watchlist/digest", headers=headers).json()
    quiet = next(item["symbol"] for item in digest["items"] if not item["is_changed"])

    response = catalysts(client, headers, quiet)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_surfaced"


def test_symbol_outside_the_watchlist_is_not_surfaced(client, seeded):
    headers, _ = start_session(client)

    response = catalysts(client, headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_surfaced"


@respx.mock
def test_first_call_is_pending_then_the_merged_feeds_are_served_from_cache(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    rss = rss_route().mock(return_value=httpx.Response(200, text=load_text("yahoo_rss.xml")))
    nse = nse_routes().mock(
        return_value=httpx.Response(200, json=load_json("nse_announcements.json"))
    )

    first = catalysts(client, headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"status": "pending", "fetched_at": None, "items": []}

    second = catalysts(client, headers).json()
    assert second["status"] == "found"
    assert second["fetched_at"] is not None
    headlines = [item["headline"] for item in second["items"]]
    assert headlines[:2] == [
        "Reliance Retail files draft papers for IPO",
        "Jio Platforms posts record quarterly profit",
    ]
    assert "Updates: Media Statement on retail business" in headlines
    assert all(
        set(item) == {"headline", "source", "url", "published_at"} for item in second["items"]
    )
    assert rss.call_count == 1
    assert nse.call_count == 1

    assert catalysts(client, headers).json() == second
    assert rss.call_count == 1


@respx.mock
def test_a_held_lock_yields_pending_without_an_upstream_call(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    rss = rss_route().mock(return_value=httpx.Response(200, text=load_text("yahoo_rss.xml")))
    nse_routes().mock(return_value=httpx.Response(200, json=[]))
    assert claim_fetch(EVENT_SYMBOL, clock.now()) is True

    response = catalysts(client, headers)

    assert response.json()["status"] == "pending"
    assert rss.call_count == 0


@respx.mock
def test_unavailable_feeds_are_cached_as_unavailable(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    rss = rss_route().mock(return_value=httpx.Response(503, text=""))
    nse_routes().mock(return_value=httpx.Response(403, text="blocked"))

    assert catalysts(client, headers).json()["status"] == "pending"
    outcome = catalysts(client, headers).json()

    assert outcome["status"] == "unavailable"
    assert outcome["items"] == []
    assert rss.call_count == 1


@respx.mock
def test_sixth_catalyst_call_in_a_minute_is_rate_limited(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    rss_route().mock(return_value=httpx.Response(200, text=load_text("yahoo_rss.xml")))
    nse_routes().mock(return_value=httpx.Response(200, json=[]))
    for _ in range(5):
        assert catalysts(client, headers).status_code == 200

    limited = catalysts(client, headers)

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
