from collections.abc import Iterable, Sequence
from datetime import datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.engine.signals import Evaluation, SessionFacts
from app.models import Baseline, DailyBar, Quote, SignalEvent, Symbol, WatchlistItem
from app.providers.base import Bar

BAR_COLUMNS = ["open", "high", "low", "close", "volume"]


def upsert_symbols(session: Session, rows: Sequence[dict]) -> None:
    statement = insert(Symbol).values(list(rows))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol"], set_=_excluded(statement, rows[0], key="symbol")
        )
    )


def upsert_bars(session: Session, symbol: str, bars: Iterable[Bar]) -> int:
    rows = [
        {
            "symbol": symbol,
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
    if not rows:
        return 0
    statement = insert(DailyBar).values(rows)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={column: getattr(statement.excluded, column) for column in BAR_COLUMNS},
        )
    )
    return len(rows)


def upsert_baselines(session: Session, rows: Sequence[dict]) -> None:
    if not rows:
        return
    statement = insert(Baseline).values(list(rows))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol"], set_=_excluded(statement, rows[0], key="symbol")
        )
    )


def upsert_quotes(session: Session, rows: Sequence[dict]) -> int:
    if not rows:
        return 0
    statement = insert(Quote).values(list(rows))
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol"], set_=_excluded(statement, rows[0], key="symbol")
        )
    )
    return len(rows)


def insert_signal_events(session: Session, rows: Sequence[dict]) -> int:
    if not rows:
        return 0
    inserted = session.execute(
        insert(SignalEvent).values(list(rows)).on_conflict_do_nothing().returning(SignalEvent.id)
    )
    return len(inserted.all())


def _excluded(statement, row: dict, key: str) -> dict:
    return {column: getattr(statement.excluded, column) for column in row if column != key}


def load_bars(session: Session, symbols: Sequence[str] | None = None) -> dict[str, pd.DataFrame]:
    query = select(
        DailyBar.symbol,
        DailyBar.date,
        DailyBar.open,
        DailyBar.high,
        DailyBar.low,
        DailyBar.close,
        DailyBar.volume,
    ).order_by(DailyBar.symbol, DailyBar.date)
    if symbols is not None:
        query = query.where(DailyBar.symbol.in_(symbols))
    frame = pd.DataFrame(session.execute(query).all(), columns=["symbol", "date", *BAR_COLUMNS])
    if frame.empty:
        return {}
    frame["date"] = pd.to_datetime(frame["date"])
    frame[BAR_COLUMNS] = frame[BAR_COLUMNS].astype(float)
    return {
        symbol: group.drop(columns="symbol").set_index("date")
        for symbol, group in frame.groupby("symbol", sort=True)
    }


def active_symbols(session: Session) -> list[str]:
    query = select(Symbol.symbol).where(Symbol.is_active.is_(True)).order_by(Symbol.symbol)
    return list(session.execute(query).scalars())


def watched_symbols(session: Session) -> list[str]:
    query = select(WatchlistItem.symbol).distinct().order_by(WatchlistItem.symbol)
    return list(session.execute(query).scalars())


def load_baselines(session: Session, symbols: Sequence[str] | None = None) -> dict[str, Baseline]:
    query = select(Baseline)
    if symbols is not None:
        query = query.where(Baseline.symbol.in_(symbols))
    return {row.symbol: row for row in session.execute(query).scalars()}


def cluster_members(session: Session) -> dict[str, list[str]]:
    query = (
        select(Baseline.cluster_id, Baseline.symbol)
        .where(Baseline.cluster_id.is_not(None))
        .order_by(Baseline.symbol)
    )
    members: dict[str, list[str]] = {}
    for cluster_id, symbol in session.execute(query):
        members.setdefault(cluster_id, []).append(symbol)
    return members


def quote_row(
    symbol: str,
    price: float,
    prev_close: float,
    day_high: float,
    day_low: float,
    volume: int,
    as_of: datetime,
    source: str,
    confidence: str,
    updated_at: datetime,
    alt: dict | None = None,
    divergence_pct: float | None = None,
) -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "prev_close": prev_close,
        "day_high": day_high,
        "day_low": day_low,
        "volume": volume,
        "as_of": as_of,
        "source": source,
        "confidence": confidence,
        "alt_price": alt["price"] if alt else None,
        "alt_source": alt["source"] if alt else None,
        "alt_as_of": alt["as_of"] if alt else None,
        "divergence_pct": divergence_pct,
        "updated_at": updated_at,
    }


def quote_cache_value(row: dict, staleness_seconds: int) -> dict:
    alt = None
    if row["alt_source"]:
        alt = {
            "price": row["alt_price"],
            "source": row["alt_source"],
            "as_of": row["alt_as_of"].isoformat(),
        }
    return {
        "price": row["price"],
        "prev_close": row["prev_close"],
        "day_high": row["day_high"],
        "day_low": row["day_low"],
        "volume": row["volume"],
        "as_of": row["as_of"].isoformat(),
        "source": row["source"],
        "confidence": row["confidence"],
        "alt": alt,
        "divergence_pct": row["divergence_pct"],
        "staleness_seconds": staleness_seconds,
    }


def signal_rows(facts: SessionFacts, evaluation: Evaluation) -> list[dict]:
    d = evaluation.decomposition
    return [
        {
            "symbol": facts.symbol,
            "signal_type": signal.type,
            "trading_date": facts.trading_date,
            "fired_at": facts.fired_at,
            "magnitude": evaluation.score,
            "payload": {
                "today_change_pct": d.today_change_pct,
                "peer_change_pct": d.peer_change_pct,
                "residual_pct": d.residual_pct,
                "z_score": d.z_score,
                "raw_z_score": d.raw_z_score,
                "rvol": evaluation.rvol,
                "headline": signal.headline,
                "detail": signal.detail,
            },
        }
        for signal in evaluation.signals
    ]
