from datetime import datetime

import pytest
import respx

from app.cache import cache
from app.clock import IST
from app.jobs import store
from app.jobs.daily import compute_baselines
from app.jobs.refresh import refresh_tick
from app.models import Quote
from tests.jobs.conftest import add_watchlist, insert_bars, insert_symbols, mock_quote

FRIDAY_MID_SESSION = datetime(2026, 9, 4, 11, 2, tzinfo=IST)


@respx.mock
def test_failed_signal_insert_leaves_neither_quote_row_nor_cache_key(
    session, universe_bars, monkeypatch
):
    insert_symbols(session)
    insert_bars(session, universe_bars)
    compute_baselines()
    add_watchlist(session, ["A.NS"])
    mock_quote("A.NS", price=110.0, prev_close=100.0, as_of=FRIDAY_MID_SESSION)
    mock_quote("^NSEI", price=100.0, prev_close=100.0, as_of=FRIDAY_MID_SESSION)

    def explode(session, rows):
        raise RuntimeError("signal insert failed")

    monkeypatch.setattr(store, "insert_signal_events", explode)

    with pytest.raises(RuntimeError, match="signal insert failed"):
        refresh_tick(FRIDAY_MID_SESSION)

    assert session.get(Quote, "A.NS") is None
    assert session.get(Quote, "^NSEI") is None
    assert cache.get("q:A.NS") is None
    assert cache.get("scheduler:last_refresh_at") is None
