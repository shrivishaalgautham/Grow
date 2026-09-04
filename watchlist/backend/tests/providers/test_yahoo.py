from datetime import date

import httpx
import pytest
import respx

from app.providers.base import ProviderError
from app.providers.ratelimit import CircuitBreaker
from app.providers.yahoo import Yahoo
from tests.providers.conftest import load_json

pytestmark = pytest.mark.usefixtures("bypass_bucket")

HOST = "query1.finance.yahoo.com"


def chart_route(symbol: str) -> respx.Route:
    return respx.get(host=HOST, path=f"/v8/finance/chart/{symbol}")


@respx.mock
def test_history_parses_bars_and_skips_null_close():
    route = chart_route("RELIANCE.NS").mock(
        return_value=httpx.Response(200, json=load_json("yahoo_chart_history.json"))
    )
    bars = Yahoo().history("RELIANCE.NS", "5d")

    assert [bar.date for bar in bars] == [
        date(2026, 8, 31),
        date(2026, 9, 1),
        date(2026, 9, 2),
        date(2026, 9, 4),
    ]
    assert bars[0].open == 1290.0
    assert bars[0].high == 1299.0
    assert bars[0].low == 1285.5
    assert bars[0].close == 1295.0
    assert bars[0].volume == 8000000
    assert bars[-1].close == 1322.0
    request = route.calls.last.request
    assert request.url.path == "/v8/finance/chart/RELIANCE.NS"
    assert "?" not in request.url.path
    assert request.url.params["range"] == "5d"
    assert request.url.params["interval"] == "1d"
    assert "Mozilla" in request.headers["User-Agent"]


@respx.mock
def test_quotes_parse_meta():
    route = chart_route("RELIANCE.NS").mock(
        return_value=httpx.Response(200, json=load_json("yahoo_chart_quote.json"))
    )
    quotes = Yahoo().quotes(["RELIANCE.NS"])

    quote = quotes["RELIANCE.NS"]
    assert quote.symbol == "RELIANCE.NS"
    assert quote.price == 1322.0
    assert quote.prev_close == 1302.5
    assert quote.day_high == 1333.0
    assert quote.day_low == 1304.1
    assert quote.volume == 13022095
    assert quote.source == "yahoo"
    assert quote.as_of.isoformat() == "2026-09-04T15:15:00+05:30"
    request = route.calls.last.request
    assert request.url.params["range"] == "1d"
    assert request.url.params["interval"] == "1m"


@respx.mock
def test_quotes_fall_back_to_intraday_bars_when_meta_lacks_day_fields():
    payload = load_json("yahoo_chart_quote.json")
    meta = payload["chart"]["result"][0]["meta"]
    for key in ("regularMarketDayHigh", "regularMarketDayLow", "regularMarketVolume"):
        del meta[key]
    chart_route("RELIANCE.NS").mock(return_value=httpx.Response(200, json=payload))

    quote = Yahoo().quotes(["RELIANCE.NS"])["RELIANCE.NS"]

    assert quote.day_high == 1317.5999755859375
    assert quote.day_low == 1304.0999755859375
    assert quote.volume == 59738 + 83008


@respx.mock
def test_quotes_skip_symbols_that_404():
    chart_route("RELIANCE.NS").mock(
        return_value=httpx.Response(200, json=load_json("yahoo_chart_quote.json"))
    )
    chart_route("TATAMOTORS.NS").mock(
        return_value=httpx.Response(404, json={"chart": {"result": None, "error": {}}})
    )

    quotes = Yahoo().quotes(["RELIANCE.NS", "TATAMOTORS.NS"])

    assert set(quotes) == {"RELIANCE.NS"}
    assert CircuitBreaker("yahoo").snapshot()["consecutive_failures"] == 0


@respx.mock
def test_quotes_raise_retryable_on_429_and_record_breaker_failure():
    chart_route("RELIANCE.NS").mock(return_value=httpx.Response(429, text="Too Many Requests"))

    with pytest.raises(ProviderError) as excinfo:
        Yahoo().quotes(["RELIANCE.NS"])

    assert excinfo.value.retryable is True
    assert excinfo.value.status == 429
    assert CircuitBreaker("yahoo").snapshot()["consecutive_failures"] == 1


@respx.mock
def test_history_raises_retryable_on_timeout():
    chart_route("RELIANCE.NS").mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderError) as excinfo:
        Yahoo().history("RELIANCE.NS")

    assert excinfo.value.retryable is True
    assert CircuitBreaker("yahoo").snapshot()["consecutive_failures"] == 1


@respx.mock
def test_open_breaker_returns_empty_without_any_http_call():
    route = chart_route("RELIANCE.NS").mock(
        return_value=httpx.Response(200, json=load_json("yahoo_chart_quote.json"))
    )
    breaker = CircuitBreaker("yahoo")
    for _ in range(3):
        breaker.record_failure()

    assert Yahoo().quotes(["RELIANCE.NS"]) == {}
    assert route.call_count == 0


@respx.mock
def test_invalid_symbol_raises_before_any_http_call():
    route = respx.get(host=HOST).mock(return_value=httpx.Response(200, json={}))
    yahoo = Yahoo()

    with pytest.raises(ValueError):
        yahoo.history("RELIANCE.NS?range=max")
    with pytest.raises(ValueError):
        yahoo.quotes(["../etc"])
    assert route.call_count == 0
