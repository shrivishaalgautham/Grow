from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.api.ratelimit import global_ip_limit
from app.db import get_session
from app.deps import ApiError, current_user, rate_limit, valid_symbol
from app.engine.digest import build_item
from app.jobs.catalysts import cached_catalysts, claim_fetch, fetch_and_cache
from app.models import Symbol, User, WatchlistItem
from app.schemas import CatalystsOut

router = APIRouter(prefix="/symbols", tags=["symbols"], dependencies=[Depends(global_ip_limit)])


@router.get(
    "/{symbol}/catalysts",
    response_model=CatalystsOut,
    dependencies=[Depends(rate_limit("catalysts", 5, 60, per="ip"))],
)
def catalysts(
    background: BackgroundTasks,
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CatalystsOut:
    now = clock.now()
    if not _is_surfaced(session, user, symbol, now):
        raise ApiError(
            403, "not_surfaced", "catalysts are shown only for changed stocks on your watchlist"
        )
    cached = cached_catalysts(symbol.symbol, now)
    if cached is not None:
        return cached
    if claim_fetch(symbol.symbol, now):
        background.add_task(fetch_and_cache, symbol.symbol, now)
    return CatalystsOut(status="pending", fetched_at=None, items=[])


def _is_surfaced(session: Session, user: User, symbol: Symbol, now: datetime) -> bool:
    watched = session.scalar(
        select(WatchlistItem.id).where(
            WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol.symbol
        )
    )
    return watched is not None and build_item(session, user, symbol, now).is_changed
