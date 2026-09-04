import logging
from datetime import UTC, datetime, timedelta

from app import clock
from app.cache import cache
from app.providers import nse_announcements, yahoo_rss
from app.providers.base import Catalyst
from app.schemas import CatalystItem, CatalystsOut

log = logging.getLogger(__name__)

CACHE_TTL_S = 1200
LOCK_TTL_S = 60
LOOKBACK_DAYS = 7
MAX_ITEMS = 10


def cache_key(symbol: str, now: datetime) -> str:
    return f"catalyst:{symbol}:{now.astimezone(clock.IST):%Y-%m-%d}"


def cached_catalysts(symbol: str, now: datetime) -> CatalystsOut | None:
    raw = cache.get(cache_key(symbol, now))
    return CatalystsOut.model_validate_json(raw) if raw else None


def claim_fetch(symbol: str, now: datetime) -> bool:
    return cache.set_nx(f"{cache_key(symbol, now)}:lock", "1", LOCK_TTL_S)


def fetch_and_cache(symbol: str, now: datetime) -> CatalystsOut:
    result = _fetch(symbol, now)
    cache.set_many({cache_key(symbol, now): result.model_dump_json()}, ttl=CACHE_TTL_S)
    log.info("catalysts symbol=%s status=%s items=%d", symbol, result.status, len(result.items))
    return result


def _fetch(symbol: str, now: datetime) -> CatalystsOut:
    since = now - timedelta(days=LOOKBACK_DAYS)
    feeds = [yahoo_rss.fetch(symbol), _announcements(symbol, since)]
    if all(feed is None for feed in feeds):
        return CatalystsOut(status="unavailable", fetched_at=now, items=[])
    recent = [item for feed in feeds if feed for item in feed if _published(item) >= since]
    items = _merged(recent)
    return CatalystsOut(status="found" if items else "none_found", fetched_at=now, items=items)


def _announcements(symbol: str, since: datetime) -> list[Catalyst] | None:
    base, _, exchange = symbol.rpartition(".")
    if exchange != "NS":
        return None
    return nse_announcements.fetch(base, since.date())


def _published(item: Catalyst) -> datetime:
    if item.published_at.tzinfo is None:
        return item.published_at.replace(tzinfo=UTC)
    return item.published_at


def _merged(catalysts: list[Catalyst]) -> list[CatalystItem]:
    unique = {item.headline.casefold(): item for item in catalysts}
    ordered = sorted(unique.values(), key=_published, reverse=True)[:MAX_ITEMS]
    return [
        CatalystItem(
            headline=item.headline,
            source=item.source,
            url=item.url,
            published_at=_published(item),
        )
        for item in ordered
    ]
