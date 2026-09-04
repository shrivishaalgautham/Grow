import argparse
import json
import logging
import random
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import clock, db
from app.cache import cache
from app.engine.baselines import Baseline, compute_baseline, daily_returns
from app.engine.peers import MIN_PEERS, cluster_symbols
from app.engine.signals import SessionFacts, evaluate
from app.jobs import store
from app.models import PeerCluster
from app.providers.base import INDEX_SYMBOL, Bar, ProviderError
from app.providers.yahoo import Yahoo

log = logging.getLogger(__name__)

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "data" / "universe.json"
INDEX_ROW = {
    "symbol": INDEX_SYMBOL,
    "name": "NIFTY 50",
    "industry": "Index",
    "isin": "",
    "is_active": False,
}
MAX_RETRIES = 3
BACKOFF_BASE_S = 1.0
HISTORY_SESSIONS = 300
CLUSTER_MAX_AGE = timedelta(days=7)
BACKFILL_SESSIONS = 120
QUOTE_TTL_S = 600


@dataclass(frozen=True)
class _Universe:
    bars: dict[str, pd.DataFrame]
    index_returns: pd.Series
    returns: pd.DataFrame


@contextmanager
def _transaction() -> Iterator[Session]:
    with db.SessionLocal() as session:
        yield session
        session.commit()


def load_universe() -> list[str]:
    rows = [{**entry, "is_active": True} for entry in json.loads(UNIVERSE_PATH.read_text())]
    with _transaction() as session:
        store.upsert_symbols(session, [*rows, INDEX_ROW])
    log.info("universe symbols=%d", len(rows))
    return [row["symbol"] for row in rows] + [INDEX_SYMBOL]


def fetch_history(symbols: Sequence[str], range_: str) -> dict[str, int]:
    yahoo = Yahoo()
    counts = {"ok": 0, "skipped": 0}
    for symbol in symbols:
        bars, status = _history_with_backoff(yahoo, symbol, range_)
        with _transaction() as session:
            written = store.upsert_bars(session, symbol, bars)
        log.info("seed symbol=%s bars=%d status=%s", symbol, written, status)
        counts["ok" if status == "ok" else "skipped"] += 1
    log.info(
        "seed_summary range=%s symbols=%d ok=%d skipped=%d",
        range_,
        len(symbols),
        counts["ok"],
        counts["skipped"],
    )
    return counts


def _history_with_backoff(yahoo: Yahoo, symbol: str, range_: str) -> tuple[list[Bar], str]:
    attempt = 0
    while True:
        try:
            bars = yahoo.history(symbol, range_)
        except ProviderError as exc:
            if not exc.retryable or attempt == MAX_RETRIES:
                return [], f"skipped:{exc.status or 'unavailable'}"
            time.sleep(BACKOFF_BASE_S * 2**attempt + random.uniform(0, 1))
            attempt += 1
            continue
        return bars, "ok" if bars else "skipped:404"


def compute_baselines(force_clusters: bool = False) -> int:
    with _transaction() as session:
        universe = _load_universe_bars(session)
        clusters = _clusters(session, universe, force_clusters)
        computed_at = clock.now()
        rows = []
        for symbol, bars in universe.bars.items():
            if len(bars) < 2:
                log.warning(
                    "baseline symbol=%s skipped=insufficient_bars bars=%d", symbol, len(bars)
                )
                continue
            peer_returns = _peer_series(symbol, universe.returns, clusters)
            baseline = compute_baseline(bars, universe.index_returns, peer_returns)
            rows.append(_baseline_row(symbol, baseline, bars, clusters.get(symbol), computed_at))
        store.upsert_baselines(session, rows)
    clustered = sum(row["cluster_id"] is not None for row in rows)
    log.info("baselines rows=%d clustered=%d", len(rows), clustered)
    return len(rows)


def _load_universe_bars(session: Session) -> _Universe:
    all_bars = store.load_bars(session, [*store.active_symbols(session), INDEX_SYMBOL])
    index_bars = all_bars.pop(INDEX_SYMBOL, None)
    if index_bars is None:
        log.warning("index_bars symbol=%s missing", INDEX_SYMBOL)
        index_returns = pd.Series(dtype=float)
    else:
        index_returns = daily_returns(index_bars["close"].tail(HISTORY_SESSIONS))
    bars = {symbol: frame.tail(HISTORY_SESSIONS) for symbol, frame in all_bars.items()}
    returns = pd.DataFrame(
        {symbol: daily_returns(frame["close"]) for symbol, frame in bars.items()}
    )
    return _Universe(bars, index_returns, returns)


def _clusters(session: Session, universe: _Universe, force: bool) -> dict[str, str | None]:
    newest = session.execute(select(func.max(PeerCluster.computed_at))).scalar_one()
    is_fresh = newest is not None and clock.now() - newest < CLUSTER_MAX_AGE
    if is_fresh and not force:
        assignment: dict[str, str | None] = dict.fromkeys(universe.bars)
        assignment.update(session.execute(select(PeerCluster.symbol, PeerCluster.cluster_id)).all())
        log.info("clusters reused computed_at=%s", newest.isoformat())
        return assignment
    assignment = _cluster_assignment(universe.returns)
    computed_at = clock.now()
    session.execute(delete(PeerCluster))
    session.add_all(
        PeerCluster(cluster_id=cluster_id, symbol=symbol, computed_at=computed_at)
        for symbol, cluster_id in assignment.items()
        if cluster_id is not None
    )
    log.info("clusters computed count=%d", len({c for c in assignment.values() if c}))
    return assignment


def _cluster_assignment(returns: pd.DataFrame) -> dict[str, str | None]:
    try:
        return cluster_symbols(returns)
    except ValueError as exc:
        log.warning("clusters skipped reason=%s", exc)
        return dict.fromkeys(returns.columns)


def _peer_series(
    symbol: str, returns: pd.DataFrame, clusters: Mapping[str, str | None]
) -> pd.Series | None:
    cluster_id = clusters.get(symbol)
    if cluster_id is None:
        return None
    others = [s for s, c in clusters.items() if c == cluster_id and s != symbol and s in returns]
    if len(others) < MIN_PEERS:
        return None
    member_returns = returns[others]
    has_enough = member_returns.count(axis=1) >= MIN_PEERS
    return member_returns.median(axis=1).where(has_enough).dropna()


def _baseline_row(
    symbol: str, b: Baseline, bars: pd.DataFrame, cluster_id: str | None, computed_at: datetime
) -> dict:
    return {
        "symbol": symbol,
        "beta": b.beta,
        "residual_sigma": b.residual_sigma,
        "raw_mean_20": b.raw_mean_20,
        "raw_sigma_20": b.raw_sigma_20,
        "sigma_daily_90": b.sigma_daily_90,
        "avg_volume_20d": b.avg_volume_20d,
        "sma_20": _or_full_history(b.sma_20, bars["close"].mean()),
        "sma_50": _or_full_history(b.sma_50, bars["close"].mean()),
        "sma_200": _or_full_history(b.sma_200, bars["close"].mean()),
        "high_52w": _or_full_history(b.high_52w, bars["high"].max()),
        "low_52w": _or_full_history(b.low_52w, bars["low"].min()),
        "prev_close": b.prev_close,
        "prev_high": b.prev_high,
        "prev_low": b.prev_low,
        "cluster_id": cluster_id,
        "confidence": b.confidence,
        "computed_at": computed_at,
    }


def _or_full_history(value: float | None, fallback: float) -> float:
    return float(fallback) if value is None else value


def backfill_signal_events(sessions: int = BACKFILL_SESSIONS) -> int:
    inserted = 0
    with _transaction() as session:
        universe = _load_universe_bars(session)
        clusters = {s: b.cluster_id for s, b in store.load_baselines(session).items()}
        for symbol in sorted(clusters):
            bars = universe.bars.get(symbol)
            if bars is None:
                continue
            rows = _eod_signal_rows(symbol, bars, universe, clusters, sessions)
            count = store.insert_signal_events(session, rows)
            inserted += count
            log.info(
                "backfill symbol=%s sessions=%d fired=%d inserted=%d",
                symbol,
                len(_session_positions(bars, sessions)),
                len(rows),
                count,
            )
    log.info("backfill_summary symbols=%d inserted=%d", len(clusters), inserted)
    return inserted


def _session_positions(bars: pd.DataFrame, sessions: int) -> range:
    return range(max(2, len(bars) - sessions), len(bars))


def _eod_signal_rows(
    symbol: str,
    bars: pd.DataFrame,
    universe: _Universe,
    clusters: Mapping[str, str | None],
    sessions: int,
) -> list[dict]:
    peer_series = _peer_series(symbol, universe.returns, clusters)
    rows: list[dict] = []
    for position in _session_positions(bars, sessions):
        session_date = bars.index[position]
        if session_date not in universe.index_returns.index:
            continue
        peer_history = (
            None if peer_series is None else peer_series[peer_series.index < session_date]
        )
        baseline = compute_baseline(bars.iloc[:position], universe.index_returns, peer_history)
        facts = _eod_facts(
            symbol,
            bars.iloc[position],
            baseline,
            float(universe.index_returns[session_date]),
            _lookup(peer_series, session_date),
            clusters[symbol],
            session_date.date(),
        )
        rows.extend(store.signal_rows(facts, evaluate(facts, baseline)))
    return rows


def _lookup(series: pd.Series | None, key) -> float | None:
    if series is None or key not in series.index:
        return None
    return float(series[key])


def _eod_facts(
    symbol: str,
    row: pd.Series,
    baseline: Baseline,
    index_return: float,
    peer_return: float | None,
    cluster_id: str | None,
    trading_date: date,
) -> SessionFacts:
    return SessionFacts(
        symbol=symbol,
        price=float(row["close"]),
        prev_close=baseline.prev_close,
        day_high=float(row["high"]),
        day_low=float(row["low"]),
        volume=float(row["volume"]),
        index_return=index_return,
        peer_return=peer_return,
        peer_cluster_id=cluster_id,
        minutes_since_open=None,
        trading_date=trading_date,
        fired_at=_session_close(trading_date),
    )


def _session_close(trading_date: date) -> datetime:
    return datetime.combine(trading_date, clock.CLOSE, tzinfo=clock.IST)


def write_eod_quotes() -> int:
    now = clock.now()
    with _transaction() as session:
        rows = [
            _eod_quote_row(symbol, bars, now) for symbol, bars in store.load_bars(session).items()
        ]
        store.upsert_quotes(session, rows)
    cache.set_many(
        {
            f"q:{row['symbol']}": json.dumps(store.quote_cache_value(row, _staleness(row, now)))
            for row in rows
        },
        ttl=QUOTE_TTL_S,
    )
    log.info("eod_quotes rows=%d", len(rows))
    return len(rows)


def _eod_quote_row(symbol: str, bars: pd.DataFrame, now: datetime) -> dict:
    last = bars.iloc[-1]
    prev_close = float(bars["close"].iloc[-2]) if len(bars) > 1 else float(last["close"])
    return store.quote_row(
        symbol,
        price=float(last["close"]),
        prev_close=prev_close,
        day_high=float(last["high"]),
        day_low=float(last["low"]),
        volume=int(last["volume"]),
        as_of=_session_close(bars.index[-1].date()),
        source="yahoo",
        confidence="closed",
        updated_at=now,
    )


def _staleness(row: dict, now: datetime) -> int:
    return max(0, int((now - row["as_of"]).total_seconds()))


def run_daily() -> None:
    with db.SessionLocal() as session:
        watched = store.watched_symbols(session)
    fetch_history([*watched, INDEX_SYMBOL], "5d")
    compute_baselines()
    backfill_signal_events()
    write_eod_quotes()


def seed(args: argparse.Namespace) -> None:
    symbols = load_universe()
    if not args.skip_fetch:
        fetch_history(args.symbols or symbols, args.range_)
    compute_baselines(force_clusters=args.force_clusters)
    backfill_signal_events(args.backfill_sessions)
    write_eod_quotes()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.jobs.daily")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--range", dest="range_", default="1y")
    parser.add_argument("--symbols", type=lambda raw: [s for s in raw.split(",") if s])
    parser.add_argument("--backfill-sessions", type=int, default=BACKFILL_SESSIONS)
    parser.add_argument("--force-clusters", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    if args.seed:
        seed(args)
    else:
        run_daily()


if __name__ == "__main__":
    main()
