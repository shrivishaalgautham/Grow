import httpx
import pytest
import respx

from app.providers import gdelt, google_news
from tests.providers.conftest import load_json, load_text

pytestmark = pytest.mark.usefixtures("bypass_bucket")


@respx.mock
def test_google_news_strips_publisher_suffix_and_drops_headlines_with_urls():
    route = respx.get(host="news.google.com", path="/rss/search").mock(
        return_value=httpx.Response(200, text=load_text("google_news.xml"))
    )

    items = google_news.fetch("Adani Enterprises")

    assert [c.headline for c in items] == [
        "Adani Enterprises board approves airport unit demerger timeline"
    ]
    assert items[0].source == "google_news"
    assert items[0].published_at.isoformat() == "2026-09-03T06:10:00+00:00"
    params = route.calls.last.request.url.params
    assert params["q"] == "Adani Enterprises NSE"
    assert params["ceid"] == "IN:en"


@respx.mock
def test_gdelt_parses_articles_and_skips_empty_titles():
    route = respx.get(host="api.gdeltproject.org", path="/api/v2/doc/doc").mock(
        return_value=httpx.Response(200, json=load_json("gdelt_doc.json"))
    )

    items = gdelt.fetch("Adani Enterprises")

    assert [c.headline for c in items] == [
        "Adani Enterprises reallocates capex toward data centres"
    ]
    assert items[0].source == "gdelt"
    assert items[0].url == "https://www.example-news.in/adani-capex"
    params = route.calls.last.request.url.params
    assert params["mode"] == "ArtList"
    assert params["format"] == "json"
    assert '"Adani Enterprises"' in params["query"]


@respx.mock
def test_both_sources_return_none_when_unreachable():
    respx.get(host="news.google.com").mock(return_value=httpx.Response(429))
    respx.get(host="api.gdeltproject.org").mock(side_effect=httpx.ConnectError("down"))

    assert google_news.fetch("Adani Enterprises") is None
    assert gdelt.fetch("Adani Enterprises") is None
