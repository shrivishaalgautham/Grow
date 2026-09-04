from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock
from app.ai import briefing as briefing_ai
from app.api.ratelimit import global_ip_limit
from app.cache import cache
from app.db import get_session
from app.deps import ApiError, current_user, valid_symbol
from app.engine.digest import build_digest, build_item
from app.models import Symbol, User, UserSymbolState, WatchlistItem
from app.quotes import load_quotes
from app.schemas import BriefingOut, DigestOut, Item, ItemAdd, SeenIn, SeenOut

WATCHLIST_CAP = 50
REFRESH_REQUEST_TTL = 600

router = APIRouter(prefix="/watchlist", tags=["watchlist"], dependencies=[Depends(global_ip_limit)])


@router.get("/digest", response_model=DigestOut)
def digest(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return build_digest(session, user, clock.now())


@router.get("/briefing", response_model=BriefingOut)
def briefing(user: User = Depends(current_user), session: Session = Depends(get_session)):
    now = clock.now()
    return briefing_ai.generate(session, user, build_digest(session, user, now), now)


@router.post("/items", status_code=201, response_model=Item)
def add_item(
    payload: ItemAdd,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Item:
    symbol = valid_symbol(payload.symbol, session)
    watched = _watched_symbols(session, user)
    if symbol.symbol in watched:
        raise ApiError(409, "already_added", "symbol is already on the watchlist")
    if len(watched) >= WATCHLIST_CAP:
        raise ApiError(400, "watchlist_full", f"watchlist holds at most {WATCHLIST_CAP} symbols")
    item = build_item(session, user, symbol, clock.now())
    session.add(WatchlistItem(user_id=user.id, symbol=symbol.symbol))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError(409, "already_added", "symbol is already on the watchlist") from None
    cache.set_nx(f"refresh:req:{symbol.symbol}", "1", REFRESH_REQUEST_TTL)
    return item


@router.delete("/items/{symbol}", status_code=204)
def remove_item(
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    session.execute(
        delete(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol.symbol
        )
    )
    session.commit()
    return Response(status_code=204)


@router.post("/seen", response_model=SeenOut)
def mark_seen(
    payload: SeenIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> SeenOut:
    now = clock.now()
    watched = _watched_symbols(session, user)
    if payload.symbols == "all":
        symbols = watched
        user.last_reviewed_at = now
    else:
        symbols = list(dict.fromkeys(payload.symbols))
        foreign = [s for s in symbols if s not in watched]
        if foreign:
            raise ApiError(400, "not_in_watchlist", f"not on your watchlist: {', '.join(foreign)}")
    quotes = load_quotes(session, symbols, now)
    missing = [s for s in symbols if s not in quotes]
    if missing:
        raise ApiError(503, "not_seeded", f"no market data for {', '.join(missing)}")
    _upsert_seen(session, user, {s: quotes[s].price for s in symbols}, now)
    session.commit()
    return SeenOut(marked=len(symbols), reviewed_at=now)


def _watched_symbols(session: Session, user: User) -> list[str]:
    return list(
        session.scalars(
            select(WatchlistItem.symbol)
            .where(WatchlistItem.user_id == user.id)
            .order_by(WatchlistItem.symbol)
        )
    )


def _upsert_seen(session: Session, user: User, prices: dict[str, float], now) -> None:
    if not prices:
        return
    statement = insert(UserSymbolState).values(
        [
            {"user_id": user.id, "symbol": symbol, "last_seen_at": now, "last_seen_price": price}
            for symbol, price in prices.items()
        ]
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[UserSymbolState.user_id, UserSymbolState.symbol],
            set_={
                "last_seen_at": statement.excluded.last_seen_at,
                "last_seen_price": statement.excluded.last_seen_price,
            },
        )
    )
