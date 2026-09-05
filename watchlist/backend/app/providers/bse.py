import json
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta

import httpx

from app import clock
from app.clock import IST
from app.config import settings
from app.providers.base import BROWSER_USER_AGENT, Bar, LiveQuote, ProviderError
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

GRAPH_URL = "https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w"
REFERER = "https://www.bseindia.com/"
DELAY = timedelta(minutes=15)
TIME_FORMAT = "%a %b %d %Y %H:%M:%S"

SCRIP_CODES: dict[str, str] = {
    "RELIANCE": "500325",
    "TCS": "532540",
    "INFY": "500209",
    "HDFCBANK": "500180",
    "ICICIBANK": "532174",
    "TMPV": "500570",
    "MARUTI": "532500",
    "SUNPHARMA": "524715",
    "ITC": "500875",
    "LT": "500510",
    "BHARTIARTL": "532454",
    "ADANIENT": "512599",
}


class Bse:
    name = "bse"

    def __init__(self, client: httpx.Client | None = None) -> None:
        client = client or httpx.Client(
            headers={
                "User-Agent": BROWSER_USER_AGENT,
                "Referer": REFERER,
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        self._upstream = Upstream(self.name, client, rate_per_sec=1.0)

    def history(self, symbol: str, range_: str = "1y") -> list[Bar]:
        raise NotImplementedError("BSE provides cross-check quotes only")

    def quotes(self, symbols: Sequence[str]) -> dict[str, LiveQuote]:
        if not settings.bse_enabled:
            return {}
        if not self._upstream.breaker.allow():
            log.warning("provider=bse op=quotes skipped=circuit_open")
            return {}
        found: dict[str, LiveQuote] = {}
        for symbol in symbols:
            code = SCRIP_CODES.get(symbol.removesuffix(".NS"))
            if code is None:
                log.info("provider=bse op=quote symbol=%s skipped=no_scrip_code", symbol)
                continue
            found[symbol] = _quote_from_graph(symbol, self._fetch_graph(symbol, code), clock.now())
        return found

    def _fetch_graph(self, symbol: str, code: str) -> dict:
        params = {"scripcode": code, "flag": "0", "fromdate": "", "todate": "", "seriesid": ""}
        response = self._upstream.get("quote", symbol, GRAPH_URL, params)
        if response.status_code != 200:
            raise self._upstream.status_error("quote", symbol, response)
        return response.json()


def _quote_from_graph(symbol: str, payload: dict, now: datetime) -> LiveQuote:
    try:
        points = json.loads(payload["Data"] or "[]")
        price = float(payload["CurrVal"])
        prev_close = float(payload["PrevClose"])
        traded = [(p["dttm"], float(p["vale1"]), int(p["vole"])) for p in points]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProviderError("bse", f"quote {symbol}: malformed graph payload") from exc
    prices = [value for _, value, _ in traded]
    return LiveQuote(
        symbol=symbol,
        price=price,
        prev_close=prev_close,
        open=prices[0] if prices else prev_close,
        day_high=max(prices, default=price),
        day_low=min(prices, default=price),
        volume=sum(volume for _, _, volume in traded),
        as_of=_last_trade_time(traded) or now - DELAY,
        source="bse",
    )


def _last_trade_time(traded: list[tuple[str, float, int]]) -> datetime | None:
    stamps = [stamp for stamp, _, volume in traded if volume > 0]
    if not stamps:
        return None
    return datetime.strptime(stamps[-1], TIME_FORMAT).replace(tzinfo=IST)
