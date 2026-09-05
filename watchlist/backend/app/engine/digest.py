from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.config import settings
from app.deps import ApiError
from app.engine.baselines import Baseline
from app.engine.peers import peer_return
from app.engine.rules_eval import facts_from, matches
from app.engine.score import attention
from app.engine.signals import Evaluation, SessionFacts, evaluate, since_seen_signal
from app.jobs import catalysts
from app.models import Baseline as BaselineRow
from app.models import (
    DailyBar,
    PeerCluster,
    SignalEvent,
    Symbol,
    User,
    UserRule,
    UserSymbolState,
    WatchlistItem,
)
from app.providers.ratelimit import CircuitBreaker
from app.quotes import INDEX_SYMBOL, load_quotes, today_returns
from app.schemas import (
    DigestOut,
    Item,
    Levels,
    Peer,
    Quote,
    Rule,
    Signal,
    SmaDistance,
)

PROVIDERS = ("yahoo", "bse")
RULE_HEADLINE_CHARS = 80


@dataclass(frozen=True)
class Market:
    now: datetime
    latest_bar_date: date
    quotes: dict[str, Quote]
    returns: dict[str, float]
    baselines: dict[str, BaselineRow]
    clusters: dict[str, list[str]]

    @property
    def status(self) -> clock.MarketStatus:
        return clock.market_status(self.now)

    @property
    def index_return(self) -> float:
        return self.returns.get(INDEX_SYMBOL, 0.0)

    def peers_of(self, symbol: str) -> list[str]:
        cluster_id = self.baselines[symbol].cluster_id
        return [member for member in self.clusters.get(cluster_id, []) if member != symbol]


@dataclass(frozen=True)
class Viewer:
    user: User
    seen: dict[str, UserSymbolState]
    windows: dict[str, datetime]
    events: dict[str, list[SignalEvent]]
    trading_days_away: dict[str, int]
    rules: list[tuple[UserRule, Rule]]


@dataclass(frozen=True)
class Assessed:
    symbol: Symbol
    quote: Quote
    baseline: BaselineRow
    peers: list[str]
    evaluation: Evaluation
    state: UserSymbolState | None
    signals: list[Signal]
    score: float


def load_market(session: Session, symbols: Sequence[str], now: datetime) -> Market:
    latest = clock.latest_bar_date(session)
    if latest is None:
        raise ApiError(503, "not_seeded", "market data has not been seeded")
    baselines = {
        row.symbol: row
        for row in session.scalars(select(BaselineRow).where(BaselineRow.symbol.in_(symbols)))
    }
    clusters = _cluster_members(session, {b.cluster_id for b in baselines.values() if b.cluster_id})
    members = [member for group in clusters.values() for member in group]
    quotes = load_quotes(session, [*symbols, *members, INDEX_SYMBOL], now)
    return Market(now, latest, quotes, today_returns(quotes), baselines, clusters)


def load_viewer(session: Session, user: User, symbols: Sequence[str]) -> Viewer:
    seen = {
        state.symbol: state
        for state in session.scalars(
            select(UserSymbolState).where(
                UserSymbolState.user_id == user.id, UserSymbolState.symbol.in_(symbols)
            )
        )
    }
    default_window = user.last_reviewed_at or user.created_at
    windows = {s: seen[s].last_seen_at if s in seen else default_window for s in symbols}
    rules = session.scalars(
        select(UserRule).where(UserRule.user_id == user.id, UserRule.enabled.is_(True))
    )
    return Viewer(
        user=user,
        seen=seen,
        windows=windows,
        events=_events_since(session, windows),
        trading_days_away={
            s: _trading_days_since(session, s, state.last_seen_at) for s, state in seen.items()
        },
        rules=[(row, Rule.model_validate(row.compiled)) for row in rules],
    )


def build_item(session: Session, user: User, symbol: Symbol, now: datetime) -> Item:
    market = load_market(session, [symbol.symbol], now)
    viewer = load_viewer(session, user, [symbol.symbol])
    return _to_item(assess(market, viewer, symbol))


def build_digest(session: Session, user: User, now: datetime) -> DigestOut:
    rows = _watchlist_symbols(session, user)
    market = load_market(session, [row.symbol for row in rows], now)
    viewer = load_viewer(session, user, [row.symbol for row in rows])
    assessed = sorted((assess(market, viewer, row) for row in rows), key=_digest_order)
    items = [
        _to_item(a, status)
        for a, status in zip(assessed, _catalyst_statuses(assessed), strict=True)
    ]
    away = None
    if user.last_reviewed_at is not None:
        away = int((now - user.last_reviewed_at).total_seconds())
    return DigestOut(
        now=now,
        market_status=market.status,
        replay_date=settings.replay_date,
        latest_bar_date=market.latest_bar_date,
        away_duration_seconds=away,
        last_reviewed_at=user.last_reviewed_at,
        changed_count=sum(item.is_changed for item in items),
        total_count=len(items),
        items=items,
        providers_degraded=any(CircuitBreaker(name).state() != "closed" for name in PROVIDERS),
    )


def assess(market: Market, viewer: Viewer, symbol: Symbol) -> Assessed:
    quote = market.quotes.get(symbol.symbol)
    baseline_row = market.baselines.get(symbol.symbol)
    if quote is None or baseline_row is None:
        raise ApiError(503, "not_seeded", f"no market data for {symbol.symbol}")
    baseline = engine_baseline(baseline_row)
    evaluation = evaluate(_facts(market, symbol.symbol, quote), baseline)
    events = viewer.events.get(symbol.symbol, [])
    signals = [_event_signal(event) for event in events]
    if quote.confidence != "disputed":
        signals += _live_signals(market, viewer, symbol.symbol, quote, baseline, evaluation)
    return Assessed(
        symbol=symbol,
        quote=quote,
        baseline=baseline_row,
        peers=market.peers_of(symbol.symbol),
        evaluation=evaluation,
        state=viewer.seen.get(symbol.symbol),
        signals=signals,
        score=max(evaluation.score, max((e.magnitude for e in events), default=0.0)),
    )


def engine_baseline(row: BaselineRow) -> Baseline:
    columns = {f.name: getattr(row, f.name) for f in fields(Baseline) if f.name != "sessions"}
    # baselines table does not persist the session count; nothing downstream of evaluate reads it
    return Baseline(**columns, sessions=0)


def _cluster_members(session: Session, cluster_ids: set[str]) -> dict[str, list[str]]:
    clusters: dict[str, list[str]] = {}
    if not cluster_ids:
        return clusters
    rows = session.scalars(
        select(PeerCluster)
        .where(PeerCluster.cluster_id.in_(cluster_ids))
        .order_by(PeerCluster.symbol)
    )
    for row in rows:
        clusters.setdefault(row.cluster_id, []).append(row.symbol)
    return clusters


def _events_since(session: Session, windows: dict[str, datetime]) -> dict[str, list[SignalEvent]]:
    events: dict[str, list[SignalEvent]] = {}
    if not windows:
        return events
    rows = session.scalars(
        select(SignalEvent)
        .where(SignalEvent.symbol.in_(windows), SignalEvent.fired_at > min(windows.values()))
        .order_by(SignalEvent.fired_at)
    )
    for event in rows:
        if event.fired_at > windows[event.symbol]:
            events.setdefault(event.symbol, []).append(event)
    return events


def _trading_days_since(session: Session, symbol: str, since: datetime) -> int:
    return session.execute(
        select(func.count(func.distinct(DailyBar.date))).where(
            DailyBar.symbol == symbol, DailyBar.date > since.astimezone(clock.IST).date()
        )
    ).scalar_one()


def _watchlist_symbols(session: Session, user: User) -> list[Symbol]:
    return list(
        session.scalars(
            select(Symbol)
            .join(WatchlistItem, WatchlistItem.symbol == Symbol.symbol)
            .where(WatchlistItem.user_id == user.id)
            .order_by(Symbol.symbol)
        )
    )


def _facts(market: Market, symbol: str, quote: Quote) -> SessionFacts:
    is_open = market.status == "open"
    return SessionFacts(
        symbol=symbol,
        price=quote.price,
        prev_close=quote.prev_close,
        open=quote.open if quote.open is not None else quote.prev_close,
        day_high=quote.day_high,
        day_low=quote.day_low,
        volume=float(quote.volume),
        index_return=market.index_return,
        peer_return=peer_return(market.returns, market.peers_of(symbol), exclude=symbol),
        peer_cluster_id=market.baselines[symbol].cluster_id,
        minutes_since_open=clock.minutes_since_open(market.now) if is_open else None,
        trading_date=clock.trading_date(market.now),
        fired_at=market.now,
    )


def _live_signals(
    market: Market,
    viewer: Viewer,
    symbol: str,
    quote: Quote,
    baseline: Baseline,
    evaluation: Evaluation,
) -> list[Signal]:
    signals: list[Signal] = []
    state = viewer.seen.get(symbol)
    if state is not None:
        since_seen = since_seen_signal(
            _change_since_seen_pct(quote, state),
            baseline.sigma_daily_90,
            viewer.trading_days_away[symbol],
            market.now,
            clock.trading_date(market.now),
        )
        if since_seen is not None:
            signals.append(since_seen)
    rule_facts = facts_from(evaluation, has_catalyst=False)
    signals += [
        _rule_signal(row, market.now)
        for row, rule in viewer.rules
        if matches(rule, symbol, rule_facts)
    ]
    return signals


def _event_signal(event: SignalEvent) -> Signal:
    return Signal(
        type=event.signal_type,
        headline=event.payload["headline"],
        detail=event.payload["detail"],
        fired_at=event.fired_at,
        trading_date=event.trading_date,
        rule_id=None,
    )


def _rule_signal(rule: UserRule, now: datetime) -> Signal:
    return Signal(
        type="USER_RULE",
        headline=rule.preview[:RULE_HEADLINE_CHARS],
        detail=rule.nl_text,
        fired_at=now,
        trading_date=clock.trading_date(now),
        rule_id=str(rule.id),
    )


def _change_since_seen_pct(quote: Quote, state: UserSymbolState) -> float:
    return (quote.price / state.last_seen_price - 1) * 100


def _digest_order(a: Assessed) -> tuple[bool, float, str]:
    is_changed = bool(a.signals)
    return (not is_changed, -a.score if is_changed else 0.0, a.symbol.symbol)


def _catalyst_statuses(assessed: list[Assessed]) -> list[str]:
    changed = [a for a in assessed if a.signals]
    by_date: dict[date, list[str]] = {}
    for a in changed:
        by_date.setdefault(max(s.trading_date for s in a.signals), []).append(a.symbol.symbol)
    found: dict[str, str] = {}
    for trading_date, symbols in by_date.items():
        found |= catalysts.cached_statuses(symbols, trading_date)
    return [found.get(a.symbol.symbol, "not_fetched") for a in assessed]


def _to_item(a: Assessed, catalyst_status: str = "not_fetched") -> Item:
    d = a.evaluation.decomposition
    is_changed = bool(a.signals)
    return Item(
        symbol=a.symbol.symbol,
        name=a.symbol.name,
        industry=a.symbol.industry,
        quote=a.quote,
        today_change_pct=d.today_change_pct,
        peer_change_pct=d.peer_change_pct,
        residual_pct=d.residual_pct,
        z_score=d.z_score,
        raw_z_score=d.raw_z_score,
        rvol=a.evaluation.rvol,
        rvol_is_approximate=a.evaluation.rvol_is_approximate,
        change_since_seen_pct=_change_since_seen_pct(a.quote, a.state) if a.state else None,
        last_seen_at=a.state.last_seen_at if a.state else None,
        attention=attention(a.score, is_changed),
        is_changed=is_changed,
        low_confidence=a.evaluation.low_confidence,
        signals=a.signals,
        levels=Levels(
            high_52w=a.baseline.high_52w,
            low_52w=a.baseline.low_52w,
            prev_high=a.baseline.prev_high,
            prev_low=a.baseline.prev_low,
        ),
        sma_distance_pct=SmaDistance(
            sma_20=_distance_pct(a.quote.price, a.baseline.sma_20),
            sma_50=_distance_pct(a.quote.price, a.baseline.sma_50),
            sma_200=_distance_pct(a.quote.price, a.baseline.sma_200),
        ),
        peer=Peer(
            method=d.peer_method,
            cluster_id=a.baseline.cluster_id,
            size=len(a.peers),
            members=a.peers,
        ),
        catalyst_status=catalyst_status,
    )


def _distance_pct(price: float, sma: float) -> float:
    return (price / sma - 1) * 100
