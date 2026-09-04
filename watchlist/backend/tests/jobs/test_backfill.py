from datetime import datetime, time

import pytest
import respx
from sqlalchemy import func, select

from app.clock import IST
from app.jobs.daily import backfill_signal_events, compute_baselines
from app.jobs.refresh import refresh_tick
from app.models import SignalEvent
from tests.jobs.conftest import (
    SESSIONS,
    SHOCK_SYMBOL,
    SYMBOLS,
    add_watchlist,
    insert_bars,
    insert_symbols,
    mock_quote,
)

LAST_MINUTE_OF_SESSION = time(15, 29)


@pytest.fixture
def seeded_through_yesterday(session, universe_bars):
    insert_symbols(session)
    insert_bars(session, universe_bars, upto=SESSIONS - 1)
    compute_baselines()
    insert_bars(session, universe_bars)


def signal_count(session) -> int:
    return session.execute(select(func.count()).select_from(SignalEvent)).scalar_one()


def test_backfill_inserts_once_and_catches_the_stock_specific_shock(
    session, seeded_through_yesterday, universe_bars
):
    inserted = backfill_signal_events(sessions=120)

    assert inserted > 0
    assert signal_count(session) == inserted
    assert backfill_signal_events(sessions=120) == 0
    assert signal_count(session) == inserted

    shock_date = universe_bars[SHOCK_SYMBOL].index[-1].date()
    shock_rows = session.execute(
        select(SignalEvent).where(
            SignalEvent.symbol == SHOCK_SYMBOL, SignalEvent.trading_date == shock_date
        )
    ).scalars()
    by_type = {row.signal_type: row for row in shock_rows}
    assert "EXCESS_MOVE" in by_type
    assert by_type["EXCESS_MOVE"].fired_at == datetime.combine(shock_date, time(15, 30), tzinfo=IST)
    assert by_type["EXCESS_MOVE"].payload["today_change_pct"] > 4.0
    assert by_type["EXCESS_MOVE"].magnitude > 0


@respx.mock
def test_live_tick_on_the_same_trading_date_inserts_nothing_new(
    session, seeded_through_yesterday, universe_bars
):
    backfill_signal_events(sessions=120)
    before = signal_count(session)
    last_date = universe_bars[SHOCK_SYMBOL].index[-1].date()
    now = datetime.combine(last_date, LAST_MINUTE_OF_SESSION, tzinfo=IST)
    add_watchlist(session, SYMBOLS)
    for symbol, frame in universe_bars.items():
        today, yesterday = frame.iloc[-1], frame.iloc[-2]
        mock_quote(
            symbol,
            price=float(today["close"]),
            prev_close=float(yesterday["close"]),
            as_of=now,
            day_high=float(today["high"]),
            day_low=float(today["low"]),
            volume=int(today["volume"]),
        )

    summary = refresh_tick(now)

    assert summary.fetched == len(universe_bars)
    assert summary.signals_inserted == 0
    assert signal_count(session) == before
