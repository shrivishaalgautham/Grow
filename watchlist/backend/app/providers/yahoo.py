import logging
from collections.abc import Sequence
from datetime import datetime

import httpx

from app.clock import IST
from app.config import settings
from app.providers.base import BROWSER_USER_AGENT, Bar, LiveQuote, ProviderError, validate_symbol
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HISTORY_INTERVAL = "1d"
QUOTE_PARAMS = {"range": "1d", "interval": "1m"}
BAR_FIELDS = ("open", "high", "low", "close", "volume")


class Yahoo:
    name = "yahoo"

    def __init__(self, client: httpx.Client | None = None) -> None:
        client = client or httpx.Client(headers={"User-Agent": BROWSER_USER_AGENT}, timeout=10.0)
        self._upstream = Upstream(self.name, client, settings.yahoo_rps)

    def history(self, symbol: str, range_: str = "1y") -> list[Bar]:
        payload = self._fetch_chart(
            symbol, "history", {"range": range_, "interval": HISTORY_INTERVAL}
        )
        if payload is None:
            return []
        _, bars = _parse_chart(payload)
        return bars

    def quotes(self, symbols: Sequence[str]) -> dict[str, LiveQuote]:
        if not self._upstream.breaker.allow():
            log.warning("provider=yahoo op=quotes skipped=circuit_open")
            return {}
        found: dict[str, LiveQuote] = {}
        for symbol in symbols:
            payload = self._fetch_chart(symbol, "quote", QUOTE_PARAMS)
            if payload is None:
                continue
            meta, bars = _parse_chart(payload)
            found[symbol] = _quote_from_chart(symbol, meta, bars)
        return found

    def _fetch_chart(self, symbol: str, op: str, params: dict[str, str]) -> dict | None:
        validate_symbol(symbol)
        response = self._upstream.get(op, symbol, CHART_URL.format(symbol=symbol), params)
        if response.status_code == 404:
            log.warning("provider=yahoo op=%s symbol=%s skipped=not_found", op, symbol)
            return None
        if response.status_code != 200:
            raise self._upstream.status_error(op, symbol, response)
        return response.json()


def _parse_chart(payload: dict) -> tuple[dict, list[Bar]]:
    try:
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result.get("timestamp") or []
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("yahoo", "malformed chart payload") from exc
    series = {field: quote.get(field) or [None] * len(timestamps) for field in BAR_FIELDS}
    bars = (_bar_at(series, timestamps, index) for index in range(len(timestamps)))
    return meta, [bar for bar in bars if bar is not None]


def _bar_at(series: dict[str, list], timestamps: list[int], index: int) -> Bar | None:
    ohlc = [series[field][index] for field in ("open", "high", "low", "close")]
    if any(value is None for value in ohlc):
        return None
    return Bar(
        date=datetime.fromtimestamp(timestamps[index], IST).date(),
        open=float(ohlc[0]),
        high=float(ohlc[1]),
        low=float(ohlc[2]),
        close=float(ohlc[3]),
        volume=int(series["volume"][index] or 0),
    )


def _quote_from_chart(symbol: str, meta: dict, bars: list[Bar]) -> LiveQuote:
    try:
        price = float(meta["regularMarketPrice"])
        prev_close = meta.get("chartPreviousClose") or meta["previousClose"]
        as_of = datetime.fromtimestamp(meta["regularMarketTime"], IST)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError("yahoo", f"quote {symbol}: malformed meta") from exc
    return LiveQuote(
        symbol=symbol,
        price=price,
        prev_close=float(prev_close),
        day_high=float(
            meta.get("regularMarketDayHigh") or max((b.high for b in bars), default=price)
        ),
        day_low=float(meta.get("regularMarketDayLow") or min((b.low for b in bars), default=price)),
        volume=int(meta.get("regularMarketVolume") or sum(b.volume for b in bars)),
        as_of=as_of,
        source="yahoo",
    )
