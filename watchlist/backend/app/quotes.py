from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock
from app.cache import cache
from app.models import DailyBar
from app.models import Quote as QuoteRow
from app.schemas import AltQuote, Quote

INDEX_SYMBOL = "^NSEI"


def cache_key(symbol: str) -> str:
    return f"q:{symbol}"


def load_quotes(session: Session, symbols: Iterable[str], now: datetime) -> dict[str, Quote]:
    wanted = list(dict.fromkeys(symbols))
    if not wanted:
        return {}
    quotes = _from_cache(wanted)
    quotes |= _from_table(session, [s for s in wanted if s not in quotes], now)
    quotes |= _from_bars(session, [s for s in wanted if s not in quotes], now)
    return quotes


def today_returns(quotes: dict[str, Quote]) -> dict[str, float]:
    return {s: q.price / q.prev_close - 1 for s, q in quotes.items() if q.prev_close > 0}


def _from_cache(symbols: list[str]) -> dict[str, Quote]:
    raw = cache.mget(cache_key(s) for s in symbols)
    return {
        symbol: Quote.model_validate_json(value)
        for symbol, value in zip(symbols, raw, strict=True)
        if value is not None
    }


def _from_table(session: Session, symbols: list[str], now: datetime) -> dict[str, Quote]:
    if not symbols:
        return {}
    rows = session.scalars(select(QuoteRow).where(QuoteRow.symbol.in_(symbols)))
    return {row.symbol: _from_row(row, now) for row in rows}


def _from_row(row: QuoteRow, now: datetime) -> Quote:
    alt = None
    if row.alt_price is not None:
        alt = AltQuote(price=row.alt_price, source=row.alt_source, as_of=row.alt_as_of)
    return Quote(
        price=row.price,
        prev_close=row.prev_close,
        day_high=row.day_high,
        day_low=row.day_low,
        volume=row.volume,
        as_of=row.as_of,
        source=row.source,
        staleness_seconds=_staleness(now, row.as_of),
        confidence=row.confidence,
        alt=alt,
        divergence_pct=row.divergence_pct,
    )


def _from_bars(session: Session, symbols: list[str], now: datetime) -> dict[str, Quote]:
    if not symbols:
        return {}
    recency = (
        func.row_number()
        .over(partition_by=DailyBar.symbol, order_by=DailyBar.date.desc())
        .label("recency")
    )
    ranked = select(DailyBar, recency).where(DailyBar.symbol.in_(symbols)).subquery()
    bars = select(ranked).where(ranked.c.recency <= 2).order_by(ranked.c.symbol, ranked.c.recency)
    latest_and_previous: dict[str, list] = {}
    for bar in session.execute(bars):
        latest_and_previous.setdefault(bar.symbol, []).append(bar)
    return {
        symbol: _from_bar(bars[0], bars[1] if len(bars) > 1 else bars[0], now)
        for symbol, bars in latest_and_previous.items()
    }


def _from_bar(latest, previous, now: datetime) -> Quote:
    as_of = datetime.combine(latest.date, clock.CLOSE, tzinfo=clock.IST)
    return Quote(
        price=latest.close,
        prev_close=previous.close,
        day_high=latest.high,
        day_low=latest.low,
        volume=latest.volume,
        as_of=as_of,
        source="yahoo",
        staleness_seconds=_staleness(now, as_of),
        confidence="closed",
        alt=None,
        divergence_pct=None,
    )


def _staleness(now: datetime, as_of: datetime) -> int:
    return max(0, int((now - as_of).total_seconds()))
