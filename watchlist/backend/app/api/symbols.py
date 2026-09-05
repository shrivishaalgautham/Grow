import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import clock
from app.ai import explain as explain_ai
from app.api.ratelimit import global_ip_limit
from app.db import get_session
from app.deps import ApiError, current_user, rate_limit, valid_symbol
from app.engine.baselines import daily_returns
from app.engine.digest import build_item, load_market
from app.engine.peers import MIN_PEERS, peer_return
from app.jobs import catalysts as catalyst_jobs
from app.models import Baseline as BaselineRow
from app.models import DailyBar, PeerCluster, Symbol, User, WatchlistItem
from app.quotes import INDEX_SYMBOL
from app.schemas import (
    CatalystsOut,
    ExplanationOut,
    HistoryBar,
    HistoryOut,
    Levels,
    PeerMember,
    PeersOut,
    SmaSeries,
    SymbolSearchOut,
)

QUERY_MAX_CHARS = 32
SEARCH_LIMIT = 10
HISTORY_MAX_DAYS = 365
SMA_WINDOWS = (20, 50, 200)
CATALYSTS_PER_MINUTE = 12

router = APIRouter(prefix="/symbols", tags=["symbols"], dependencies=[Depends(global_ip_limit)])


@router.get("/search", response_model=list[SymbolSearchOut])
def search(
    q: str = Query(default=""),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[SymbolSearchOut]:
    if len(q) > QUERY_MAX_CHARS:
        raise ApiError(400, "invalid_request", f"q must be at most {QUERY_MAX_CHARS} characters")
    if not q:
        return []
    pattern = f"%{_escape_like(q)}%"
    rows = session.scalars(
        select(Symbol)
        .where(
            Symbol.is_active.is_(True),
            or_(Symbol.symbol.ilike(pattern, escape="\\"), Symbol.name.ilike(pattern, escape="\\")),
        )
        .order_by(Symbol.symbol)
        .limit(SEARCH_LIMIT)
    )
    return [SymbolSearchOut(symbol=r.symbol, name=r.name, industry=r.industry) for r in rows]


@router.get("/{symbol}/history", response_model=HistoryOut)
def history(
    days: int = Query(default=90, ge=1, le=HISTORY_MAX_DAYS),
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> HistoryOut:
    baseline = session.get(BaselineRow, symbol.symbol)
    bars = _bars_frame(session, [symbol.symbol]).get(symbol.symbol)
    if baseline is None or bars is None:
        raise ApiError(503, "not_seeded", f"no market data for {symbol.symbol}")
    returns = daily_returns(bars["close"])
    reference = _reference_returns(session, symbol.symbol, baseline, returns.index)
    residual = (returns - reference.reindex(returns.index).fillna(0.0)) * 100
    window = bars.tail(days)
    return HistoryOut(
        bars=[
            HistoryBar(
                date=day.date(),
                close=float(row["close"]),
                volume=int(row["volume"]),
                today_change_pct=_at(returns * 100, day),
                residual_pct=_at(residual, day),
            )
            for day, row in window.iterrows()
        ],
        levels=_levels(baseline),
        sma=SmaSeries(**{f"sma_{w}": _sma(bars["close"], w, len(window)) for w in SMA_WINDOWS}),
    )


@router.get("/{symbol}/peers", response_model=PeersOut)
def peers(
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> PeersOut:
    market = load_market(session, [symbol.symbol], clock.now())
    baseline = market.baselines.get(symbol.symbol)
    if baseline is None:
        raise ApiError(503, "not_seeded", f"no market data for {symbol.symbol}")
    members = market.peers_of(symbol.symbol)
    peer_change = peer_return(market.returns, members, exclude=symbol.symbol)
    method = "beta" if peer_change is None else "cluster"
    if peer_change is None:
        peer_change = baseline.beta * market.index_return
    names = {
        row.symbol: row.name
        for row in session.scalars(select(Symbol).where(Symbol.symbol.in_(members)))
    }
    return PeersOut(
        method=method,
        cluster_id=baseline.cluster_id,
        size=len(members),
        peer_change_pct=peer_change * 100,
        members=[
            PeerMember(symbol=m, name=names[m], today_change_pct=market.returns[m] * 100)
            for m in members
            if m in market.returns
        ],
    )


@router.get(
    "/{symbol}/catalysts",
    response_model=CatalystsOut,
    dependencies=[Depends(rate_limit("catalysts", CATALYSTS_PER_MINUTE, 60, per="ip"))],
)
def catalysts(
    background: BackgroundTasks,
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> CatalystsOut:
    now = clock.now()
    item = _surfaced_item(session, user, symbol, now)
    trading_date = _latest_signal_date(item)
    hit = catalyst_jobs.cached(symbol.symbol, trading_date)
    if hit is not None:
        return hit
    if catalyst_jobs.try_begin(symbol.symbol, trading_date):
        background.add_task(
            catalyst_jobs.fetch_and_cache, symbol.symbol, symbol.name, trading_date, now
        )
    return CatalystsOut(status="pending", fetched_at=None, items=[])


@router.get(
    "/{symbol}/explanation",
    response_model=ExplanationOut,
    dependencies=[Depends(rate_limit("explanation", CATALYSTS_PER_MINUTE, 60, per="ip"))],
)
def explanation(
    background: BackgroundTasks,
    symbol: Symbol = Depends(valid_symbol),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> ExplanationOut:
    now = clock.now()
    item = _surfaced_item(session, user, symbol, now)
    trading_date = _latest_signal_date(item)
    catalysts = catalyst_jobs.cached(symbol.symbol, trading_date)
    if catalysts is None:
        if catalyst_jobs.try_begin(symbol.symbol, trading_date):
            background.add_task(
                catalyst_jobs.fetch_and_cache, symbol.symbol, symbol.name, trading_date, now
            )
        return ExplanationOut(
            status="pending",
            text=None,
            source=None,
            catalyst_status="pending",
            items=[],
            generated_at=None,
            was_cached=False,
        )
    return explain_ai.explain(user, item, catalysts, trading_date, now)


def _surfaced_item(session: Session, user: User, symbol: Symbol, now):
    is_watched = session.scalar(
        select(WatchlistItem.id).where(
            WatchlistItem.user_id == user.id, WatchlistItem.symbol == symbol.symbol
        )
    )
    if is_watched is None:
        raise ApiError(403, "not_surfaced", "only watched stocks are explained")
    item = build_item(session, user, symbol, now)
    if not item.is_changed:
        raise ApiError(403, "not_surfaced", "only stocks that changed are explained")
    return item


def _latest_signal_date(item):
    return max(signal.trading_date for signal in item.signals)


def _escape_like(raw: str) -> str:
    return raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _bars_frame(session: Session, symbols: list[str]) -> dict[str, pd.DataFrame]:
    rows = session.execute(
        select(DailyBar.symbol, DailyBar.date, DailyBar.close, DailyBar.volume)
        .where(DailyBar.symbol.in_(symbols))
        .order_by(DailyBar.symbol, DailyBar.date)
    ).all()
    if not rows:
        return {}
    frame = pd.DataFrame(rows, columns=["symbol", "date", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["date"])
    return {
        symbol: group.set_index("date")[["close", "volume"]]
        for symbol, group in frame.groupby("symbol")
    }


def _reference_returns(
    session: Session, symbol: str, baseline: BaselineRow, dates: pd.DatetimeIndex
) -> pd.Series:
    others = _cluster_peers(session, symbol, baseline.cluster_id)
    frames = _bars_frame(session, [*others, INDEX_SYMBOL])
    index_bars = frames.get(INDEX_SYMBOL)
    beta_reference = (
        baseline.beta * daily_returns(index_bars["close"])
        if index_bars is not None
        else pd.Series(0.0, index=dates)
    )
    member_returns = pd.DataFrame(
        {s: daily_returns(frames[s]["close"]) for s in others if s in frames}
    )
    if member_returns.empty:
        return beta_reference
    has_enough = member_returns.count(axis=1) >= MIN_PEERS
    peer_median = member_returns.median(axis=1).where(has_enough)
    return peer_median.combine_first(beta_reference)


def _cluster_peers(session: Session, symbol: str, cluster_id: str | None) -> list[str]:
    if cluster_id is None:
        return []
    return [
        s
        for s in session.scalars(
            select(PeerCluster.symbol).where(PeerCluster.cluster_id == cluster_id)
        )
        if s != symbol
    ]


def _at(series: pd.Series, day) -> float:
    return float(series[day]) if day in series.index else 0.0


def _sma(close: pd.Series, window: int, length: int) -> list[float | None]:
    values = close.rolling(window).mean().tail(length)
    return [None if pd.isna(v) else float(v) for v in values]


def _levels(baseline: BaselineRow) -> Levels:
    return Levels(
        high_52w=baseline.high_52w,
        low_52w=baseline.low_52w,
        prev_high=baseline.prev_high,
        prev_low=baseline.prev_low,
    )
