import httpx
import pytest
import respx

from app.config import settings
from app.providers.bse import Bse
from tests.providers.conftest import load_json

pytestmark = pytest.mark.usefixtures("bypass_bucket")


def graph_route() -> respx.Route:
    return respx.get(host="api.bseindia.com", path="/BseIndiaAPI/api/StockReachGraph/w")


@respx.mock
def test_quotes_parse_graph_payload():
    route = graph_route().mock(return_value=httpx.Response(200, json=load_json("bse_graph.json")))

    quote = Bse().quotes(["RELIANCE.NS"])["RELIANCE.NS"]

    assert quote.symbol == "RELIANCE.NS"
    assert quote.price == 1322.0
    assert quote.prev_close == 1301.05
    assert quote.day_high == 1322.0
    assert quote.day_low == 1311.1
    assert quote.volume == 5348 + 1603 + 3250 + 1
    assert quote.source == "bse"
    assert quote.as_of.isoformat() == "2026-09-04T15:52:45+05:30"
    request = route.calls.last.request
    assert request.url.params["scripcode"] == "500325"
    assert request.headers["Referer"] == "https://www.bseindia.com/"


@respx.mock
def test_symbol_without_scrip_code_is_skipped():
    route = graph_route().mock(return_value=httpx.Response(200, json=load_json("bse_graph.json")))

    assert Bse().quotes(["UNKNOWN.NS"]) == {}
    assert route.call_count == 0


@respx.mock
def test_disabled_bse_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "bse_enabled", False)
    route = graph_route().mock(return_value=httpx.Response(200, json=load_json("bse_graph.json")))

    assert Bse().quotes(["RELIANCE.NS"]) == {}
    assert route.call_count == 0


def test_history_is_not_supported():
    with pytest.raises(NotImplementedError):
        Bse().history("RELIANCE.NS")
