from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from app.engine.baselines import Baseline, compute_baseline, daily_returns
from app.engine.peers import MIN_PEERS
from app.engine.signals import EXCESS_FLOOR_PCT, Evaluation, SessionFacts, evaluate

NAIVE_THRESHOLD_PCT = 2.0
RAW_Z_THRESHOLD = 2.0
MARKET_WIDE_PEER_PCT = 1.0
MAX_CAUGHT_EXTRA = 20
SESSION_CLOSE = time(15, 30)
IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class Replay:
    days: int
    symbols_count: int
    from_date: date
    to_date: date
    naive_pct_2: dict[str, int]
    raw_z_2: dict[str, int]
    engine: dict[str, int]
    suppressed: dict[str, int]
    caught_extra: list[dict]


@dataclass(frozen=True)
class _Session:
    symbol: str
    trading_date: date
    evaluation: Evaluation


def replay(
    bars: Mapping[str, pd.DataFrame],
    index_bars: pd.DataFrame,
    clusters: Mapping[str, str | None],
    days: int = 90,
) -> Replay:
    index_returns = daily_returns(index_bars["close"])
    returns = pd.DataFrame({symbol: daily_returns(df["close"]) for symbol, df in bars.items()})
    sessions = [
        session
        for symbol, symbol_bars in bars.items()
        for session in _replay_symbol(
            symbol,
            symbol_bars,
            index_returns,
            _peer_series(symbol, returns, clusters),
            clusters.get(symbol),
            days,
        )
    ]
    if not sessions:
        raise ValueError("no sessions to replay: bars and index_bars share no dates")
    return _summarize(sessions, days, len(bars))


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


def _replay_symbol(
    symbol: str,
    symbol_bars: pd.DataFrame,
    index_returns: pd.Series,
    peer_series: pd.Series | None,
    cluster_id: str | None,
    days: int,
) -> list[_Session]:
    sessions = []
    for position in range(max(2, len(symbol_bars) - days), len(symbol_bars)):
        session_date = symbol_bars.index[position]
        if session_date not in index_returns.index:
            continue
        history = symbol_bars.iloc[:position]
        peer_history = (
            None if peer_series is None else peer_series[peer_series.index < session_date]
        )
        baseline = compute_baseline(history, index_returns, peer_history)
        peer_today = _lookup(peer_series, session_date)
        facts = _facts(
            symbol,
            symbol_bars.iloc[position],
            baseline,
            float(index_returns[session_date]),
            peer_today,
            cluster_id,
            pd.Timestamp(session_date).date(),
        )
        sessions.append(_Session(symbol, facts.trading_date, evaluate(facts, baseline)))
    return sessions


def _lookup(series: pd.Series | None, key) -> float | None:
    if series is None or key not in series.index:
        return None
    return float(series[key])


def _facts(
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
        fired_at=datetime.combine(trading_date, SESSION_CLOSE, tzinfo=IST),
    )


def _summarize(sessions: list[_Session], days: int, symbols_count: int) -> Replay:
    naive = [s for s in sessions if _is_naive_alert(s)]
    engine = [s for s in sessions if _excess_fired(s)]
    suppressed = [s for s in naive if not _excess_fired(s)]
    caught_extra = sorted(
        (_caught_row(s) for s in engine if not _is_naive_alert(s)),
        key=lambda row: row["z_score"],
        reverse=True,
    )[:MAX_CAUGHT_EXTRA]
    return Replay(
        days=days,
        symbols_count=symbols_count,
        from_date=min(s.trading_date for s in sessions),
        to_date=max(s.trading_date for s in sessions),
        naive_pct_2={"alerts": len(naive)},
        raw_z_2={
            "alerts": sum(
                s.evaluation.decomposition.raw_z_score >= RAW_Z_THRESHOLD for s in sessions
            )
        },
        engine={"alerts": len(engine)},
        suppressed={
            "total": len(suppressed),
            "market_wide": sum(_is_market_wide(s) for s in suppressed),
            "below_floor": sum(_is_below_floor(s) and not _is_market_wide(s) for s in suppressed),
            "unconfirmed_volume": 0,
        },
        caught_extra=caught_extra,
    )


def _is_naive_alert(session: _Session) -> bool:
    return abs(session.evaluation.decomposition.today_change_pct) >= NAIVE_THRESHOLD_PCT


def _excess_fired(session: _Session) -> bool:
    return any(signal.type == "EXCESS_MOVE" for signal in session.evaluation.signals)


def _is_market_wide(session: _Session) -> bool:
    d = session.evaluation.decomposition
    return abs(d.peer_change_pct) >= MARKET_WIDE_PEER_PCT and _is_below_floor(session)


def _is_below_floor(session: _Session) -> bool:
    return abs(session.evaluation.decomposition.residual_pct) < EXCESS_FLOOR_PCT


def _caught_row(session: _Session) -> dict:
    d = session.evaluation.decomposition
    return {
        "symbol": session.symbol,
        "date": session.trading_date,
        "today_change_pct": d.today_change_pct,
        "peer_change_pct": d.peer_change_pct,
        "residual_pct": d.residual_pct,
        "z_score": d.z_score,
        "rvol": session.evaluation.rvol,
    }
