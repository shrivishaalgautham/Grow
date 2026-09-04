from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import clock
from app.api.ratelimit import global_ip_limit
from app.api.sample import DEMO_SYMBOLS
from app.cache import cache
from app.db import get_session
from app.deps import ApiError, current_user
from app.evidence.replay import replay
from app.jobs import store
from app.models import User
from app.quotes import INDEX_SYMBOL
from app.schemas import EvidenceOut

MAX_DAYS = 180
CACHE_TTL_S = 86400

router = APIRouter(prefix="/evidence", tags=["evidence"], dependencies=[Depends(global_ip_limit)])


@router.get("/noise-reduction", response_model=EvidenceOut)
def noise_reduction(
    days: int = Query(default=90, ge=10, le=MAX_DAYS),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> EvidenceOut:
    latest = clock.latest_bar_date(session)
    if latest is None:
        raise ApiError(503, "not_seeded", "market data has not been seeded")
    key = f"evidence:{days}:{latest.isoformat()}"
    cached = cache.get(key)
    if cached:
        return EvidenceOut.model_validate_json(cached)
    result = _compute(session, days)
    cache.set_many({key: result.model_dump_json()}, ttl=CACHE_TTL_S)
    return result


def _compute(session: Session, days: int) -> EvidenceOut:
    symbols = [f"{name}.NS" for name in DEMO_SYMBOLS]
    bars = store.load_bars(session, [*symbols, INDEX_SYMBOL])
    index_bars = bars.pop(INDEX_SYMBOL, None)
    if index_bars is None or not bars:
        raise ApiError(503, "not_seeded", "market data has not been seeded")
    clusters = {s: b.cluster_id for s, b in store.load_baselines(session, list(bars)).items()}
    try:
        result = replay(bars, index_bars, clusters, days)
    except ValueError as exc:
        raise ApiError(503, "not_seeded", "market data has no overlapping sessions") from exc
    return EvidenceOut(**asdict(result), computed_at=clock.now())
