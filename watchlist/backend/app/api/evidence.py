import hashlib
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import clock
from app.api.ratelimit import global_ip_limit
from app.cache import cache
from app.db import get_session
from app.deps import ApiError, current_user
from app.evidence.replay import replay
from app.jobs import store
from app.models import User
from app.providers.base import INDEX_SYMBOL
from app.schemas import EvidenceOut

log = logging.getLogger(__name__)

CACHE_TTL_S = 3600
MIN_DAYS = 30
MAX_DAYS = 250

router = APIRouter(prefix="/evidence", tags=["evidence"], dependencies=[Depends(global_ip_limit)])


@router.get("/noise-reduction", response_model=EvidenceOut)
def noise_reduction(
    days: int = Query(default=90, ge=MIN_DAYS, le=MAX_DAYS),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> EvidenceOut:
    latest = clock.latest_bar_date(session)
    if latest is None:
        raise ApiError(503, "not_seeded", "market data has not been seeded")
    symbols = _symbols_for(session, user)
    key = _cache_key(symbols, latest.isoformat(), days)
    hit = cache.get(key)
    if hit:
        return EvidenceOut.model_validate_json(hit)
    result = _compute(session, symbols, days)
    cache.set_many({key: result.model_dump_json()}, ttl=CACHE_TTL_S)
    return result


def _symbols_for(session: Session, user: User) -> list[str]:
    from app.engine.digest import _watchlist_symbols

    watched = [row.symbol for row in _watchlist_symbols(session, user)]
    return watched or store.active_symbols(session)


def _cache_key(symbols: list[str], latest: str, days: int) -> str:
    digest = hashlib.sha256(",".join(sorted(symbols)).encode()).hexdigest()[:16]
    return f"evidence:v2:{digest}:{latest}:{days}"


def _compute(session: Session, symbols: list[str], days: int) -> EvidenceOut:
    clusters = {s: b.cluster_id for s, b in store.load_baselines(session).items()}
    wanted = set(symbols)
    for cluster_id in {clusters.get(s) for s in symbols if clusters.get(s)}:
        wanted |= {s for s, c in clusters.items() if c == cluster_id}
    bars = store.load_bars(session, [*wanted, INDEX_SYMBOL])
    index_bars = bars.pop(INDEX_SYMBOL, None)
    if index_bars is None or not bars:
        raise ApiError(503, "not_seeded", "market data has not been seeded")
    summary = replay(bars, index_bars, clusters, days, symbols=[s for s in symbols if s in bars])
    log.info(
        "evidence symbols=%d days=%d naive=%d raw_z=%d engine=%d",
        summary.symbols_count,
        days,
        summary.naive_pct_2["alerts"],
        summary.raw_z_2["alerts"],
        summary.engine["alerts"],
    )
    return EvidenceOut(
        days=summary.days,
        symbols_count=summary.symbols_count,
        from_date=summary.from_date,
        to_date=summary.to_date,
        computed_at=clock.now(),
        naive_pct_2=summary.naive_pct_2,
        raw_z_2=summary.raw_z_2,
        engine=summary.engine,
        suppressed=summary.suppressed,
        caught_extra=summary.caught_extra,
    )
