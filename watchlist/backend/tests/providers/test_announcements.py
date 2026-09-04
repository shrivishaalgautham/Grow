from datetime import date

import httpx
import pytest
import respx

from app.providers import nse_announcements
from tests.providers.conftest import load_json

pytestmark = pytest.mark.usefixtures("bypass_bucket")

SINCE = date(2026, 8, 5)


def home_route() -> respx.Route:
    return respx.get("https://www.nseindia.com/").mock(return_value=httpx.Response(200, text=""))


def announcements_route() -> respx.Route:
    return respx.get(host="www.nseindia.com", path="/api/corporate-announcements")


@respx.mock
def test_fetch_sanitizes_and_filters_by_since():
    home_route()
    route = announcements_route().mock(
        return_value=httpx.Response(200, json=load_json("nse_announcements.json"))
    )

    catalysts = nse_announcements.fetch("RELIANCE", SINCE)

    assert [item.headline for item in catalysts] == [
        "Updates: Media Statement on retail business",
        (
            "Updates: This is further to the disclosure dated August 13, 2026 made by the Company "
            "regarding the proposed scheme of arrangement between the Company and its wh"
        ),
    ]
    assert all(len(item.headline) <= 160 for item in catalysts)
    assert catalysts[0].source == "nse"
    assert catalysts[0].url == "https://nsearchives.nseindia.com/corporate/RIL_SE_28082026_MS.pdf"
    assert catalysts[0].published_at.isoformat() == "2026-08-28T19:45:51+05:30"
    request = route.calls.last.request
    assert request.url.params["symbol"] == "RELIANCE"
    assert request.url.params["index"] == "equities"
    assert request.url.params["from_date"] == "05-08-2026"
    assert request.headers["Accept"].startswith("application/json")


@respx.mock
def test_fetch_returns_empty_when_nothing_since():
    home_route()
    announcements_route().mock(
        return_value=httpx.Response(200, json=load_json("nse_announcements.json"))
    )

    assert nse_announcements.fetch("RELIANCE", date(2026, 9, 1)) == []


@respx.mock
def test_forbidden_returns_none():
    home_route()
    announcements_route().mock(return_value=httpx.Response(403, text="blocked"))

    assert nse_announcements.fetch("RELIANCE", SINCE) is None


@respx.mock
def test_timeout_returns_none():
    home_route()
    announcements_route().mock(side_effect=httpx.ReadTimeout("slow"))

    assert nse_announcements.fetch("RELIANCE", SINCE) is None


@respx.mock
def test_home_page_status_does_not_block_the_api_call():
    respx.get("https://www.nseindia.com/").mock(return_value=httpx.Response(403, text=""))
    announcements_route().mock(return_value=httpx.Response(200, json=[]))

    assert nse_announcements.fetch("RELIANCE", SINCE) == []


@respx.mock
def test_invalid_symbol_raises_before_any_http_call():
    route = respx.get(host="www.nseindia.com").mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(ValueError):
        nse_announcements.fetch("RELIANCE.NS?x=1", SINCE)
    assert route.call_count == 0
