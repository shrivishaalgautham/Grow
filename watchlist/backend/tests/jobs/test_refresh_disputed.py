from datetime import datetime

import httpx
import pytest
import respx
from sqlalchemy import select

from app.clock import IST
from app.jobs.daily import compute_baselines
from app.jobs.refresh import refresh_tick
from app.models import Quote, SignalEvent
from tests.jobs.conftest import (
    BSE_HOST,
    SHOCK_SYMBOL,
    SYMBOLS,
    add_watchlist,
    bse_graph_payload,
    insert_bars,
    insert_symbols,
    mock_quote,
)

CROSS_CHECKED = "RELIANCE.NS"
NOW = datetime(2026, 9, 4, 11, 2, tzinfo=IST)


@pytest.fixture
def watched_reliance(session, universe_bars):
    insert_symbols(session, [*SYMBOLS, CROSS_CHECKED])
    insert_bars(session, {**universe_bars, CROSS_CHECKED: universe_bars[SHOCK_SYMBOL]})
    compute_baselines()
    add_watchlist(session, [CROSS_CHECKED])
    mock_quote(CROSS_CHECKED, price=100.0, prev_close=90.0, as_of=NOW)
    mock_quote("^NSEI", price=100.0, prev_close=100.0, as_of=NOW)


def mock_bse(price: float) -> respx.Route:
    return respx.get(host=BSE_HOST, path="/BseIndiaAPI/api/StockReachGraph/w").mock(
        return_value=httpx.Response(200, json=bse_graph_payload(price, 90.0))
    )


def signal_types(session, symbol: str) -> set[str]:
    query = select(SignalEvent.signal_type).where(SignalEvent.symbol == symbol)
    return set(session.execute(query).scalars())


@respx.mock
def test_disputed_quote_is_stored_but_fires_no_signals(session, watched_reliance):
    mock_bse(101.0)

    summary = refresh_tick(NOW)

    assert summary.disputed == 1
    assert session.get(Quote, CROSS_CHECKED).confidence == "disputed"
    assert signal_types(session, CROSS_CHECKED) == set()


@respx.mock
def test_agreeing_cross_check_lets_the_same_move_fire(session, watched_reliance):
    mock_bse(100.2)

    summary = refresh_tick(NOW)

    assert summary.disputed == 0
    assert session.get(Quote, CROSS_CHECKED).confidence == "fresh"
    assert "EXCESS_MOVE" in signal_types(session, CROSS_CHECKED)
