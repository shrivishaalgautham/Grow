import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta

from app.cache import cache
from app.clock import IST
from app.config import settings
from app.providers import gdelt, google_news, nse_announcements, yahoo_rss
from app.providers.base import Catalyst
from app.schemas import CatalystItem, CatalystsOut

log = logging.getLogger(__name__)

CACHE_TTL_S = 1200
LOCK_TTL_S = 60
LOOKBACK = timedelta(days=3)
MAX_ITEMS = 8


def cache_key(symbol: str, trading_date: date) -> str:
    return f"catalyst:{symbol}:{trading_date.isoformat()}"


def cached(symbol: str, trading_date: date) -> CatalystsOut | None:
    raw = cache.get(cache_key(symbol, trading_date))
    return CatalystsOut.model_validate_json(raw) if raw else None


def cached_statuses(symbols: Sequence[str], trading_date: date) -> dict[str, str]:
    symbols = list(symbols)
    if not symbols:
        return {}
    raw = cache.mget(cache_key(s, trading_date) for s in symbols)
    return {
        symbol: CatalystsOut.model_validate_json(value).status
        for symbol, value in zip(symbols, raw, strict=True)
        if value
    }


def try_begin(symbol: str, trading_date: date) -> bool:
    return cache.set_nx(f"{cache_key(symbol, trading_date)}:lock", "1", LOCK_TTL_S)


def fetch_and_cache(symbol: str, company: str, trading_date: date, now: datetime) -> CatalystsOut:
    since = trading_date - LOOKBACK
    feeds = [yahoo_rss.fetch(symbol), nse_announcements.fetch(symbol.split(".")[0], since)]
    if settings.google_news_enabled:
        feeds.append(google_news.fetch(company))
    if settings.gdelt_enabled:
        feeds.append(gdelt.fetch(company))
    reachable = [feed for feed in feeds if feed is not None]
    items = _recent([c for feed in reachable for c in feed], since)
    if not reachable:
        status = "unavailable"
    elif items:
        status = "found"
    else:
        status = "none_found"
    result = CatalystsOut(
        status=status,
        fetched_at=now,
        items=[
            CatalystItem(
                headline=c.headline, source=c.source, url=c.url, published_at=c.published_at
            )
            for c in items[:MAX_ITEMS]
        ],
    )
    cache.set_many({cache_key(symbol, trading_date): result.model_dump_json()}, ttl=CACHE_TTL_S)
    cache.delete(f"{cache_key(symbol, trading_date)}:lock")
    log.info("catalysts symbol=%s status=%s items=%d", symbol, status, len(result.items))
    return result


def _recent(catalysts: list[Catalyst], since: date) -> list[Catalyst]:
    cutoff = datetime.combine(since, datetime.min.time(), tzinfo=IST)
    recent = [c for c in catalysts if _aware(c.published_at) >= cutoff]
    return sorted(recent, key=lambda c: _aware(c.published_at), reverse=True)


def _aware(stamp: datetime) -> datetime:
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=IST)
