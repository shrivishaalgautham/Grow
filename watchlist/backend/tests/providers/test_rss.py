import httpx
import pytest
import respx

from app.providers import yahoo_rss
from app.providers.base import sanitize_headline
from tests.providers.conftest import load_text

pytestmark = pytest.mark.usefixtures("bypass_bucket")


def feed_route() -> respx.Route:
    return respx.get(host="feeds.finance.yahoo.com", path="/rss/2.0/headline")


@respx.mock
def test_fetch_parses_items():
    route = feed_route().mock(return_value=httpx.Response(200, text=load_text("yahoo_rss.xml")))

    catalysts = yahoo_rss.fetch("RELIANCE.NS")

    assert len(catalysts) == 2
    assert catalysts[0].headline == "Reliance Retail files draft papers for IPO"
    assert catalysts[0].url == "https://finance.yahoo.com/news/reliance-retail-ipo-123456.html"
    assert catalysts[0].source == "yahoo_rss"
    assert catalysts[0].published_at.isoformat() == "2026-09-03T10:15:00+00:00"
    assert catalysts[1].headline == "Jio Platforms posts record quarterly profit"
    request = route.calls.last.request
    assert request.url.params["s"] == "RELIANCE.NS"
    assert request.url.params["region"] == "IN"
    assert "Mozilla" in request.headers["User-Agent"]


@respx.mock
def test_not_found_returns_none():
    feed_route().mock(return_value=httpx.Response(404, text=""))

    assert yahoo_rss.fetch("RELIANCE.NS") is None


@respx.mock
def test_server_error_returns_none():
    feed_route().mock(return_value=httpx.Response(503, text=""))

    assert yahoo_rss.fetch("RELIANCE.NS") is None


@respx.mock
def test_timeout_returns_none():
    feed_route().mock(side_effect=httpx.ConnectTimeout("slow"))

    assert yahoo_rss.fetch("RELIANCE.NS") is None


@respx.mock
def test_malformed_xml_returns_none():
    feed_route().mock(return_value=httpx.Response(200, text="<rss><channel><item>"))

    assert yahoo_rss.fetch("RELIANCE.NS") is None


@respx.mock
def test_invalid_symbol_raises_before_any_http_call():
    route = feed_route().mock(return_value=httpx.Response(200, text=""))

    with pytest.raises(ValueError):
        yahoo_rss.fetch("reliance")
    assert route.call_count == 0


def test_sanitizer_drops_url_bearing_headlines():
    assert sanitize_headline("Click http://evil.example now") is None
    assert sanitize_headline("Click HTTPS://evil.example now") is None


def test_sanitizer_strips_control_chars_and_collapses_whitespace():
    assert sanitize_headline("Jio\x07 posts\t\trecord\n\n  profit\x1b[0m") == (
        "Jio posts record profit [0m"
    )


def test_sanitizer_truncates_to_160_chars():
    assert sanitize_headline("x" * 300) == "x" * 160


def test_sanitizer_drops_empty_headlines():
    assert sanitize_headline("\x00\x01  \t") is None
