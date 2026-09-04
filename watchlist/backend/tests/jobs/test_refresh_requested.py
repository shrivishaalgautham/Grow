import json
from datetime import datetime

import respx

from app.cache import cache
from app.clock import IST
from app.jobs.refresh import refresh_tick
from app.models import Quote
from tests.jobs.conftest import add_watchlist, insert_symbols, mock_quote

NOT_A_WARM_TICK = datetime(2026, 9, 4, 11, 2, tzinfo=IST)


@respx.mock
def test_requested_symbol_is_refreshed_this_tick_and_the_key_deleted(session):
    insert_symbols(session)
    add_watchlist(session, ["A.NS"])
    cache.set_nx("refresh:req:E.NS", "1", 600)
    routes = {
        symbol: mock_quote(symbol, price=100.0, prev_close=100.0, as_of=NOT_A_WARM_TICK)
        for symbol in ("A.NS", "E.NS", "F.NS", "^NSEI")
    }

    summary = refresh_tick(NOT_A_WARM_TICK)

    assert summary.symbols == 3
    assert routes["E.NS"].call_count == 1
    assert routes["F.NS"].call_count == 0
    assert cache.get("refresh:req:E.NS") is None
    assert session.get(Quote, "E.NS").price == 100.0
    assert json.loads(cache.get("q:E.NS"))["confidence"] == "fresh"
    assert cache.get("scheduler:last_refresh_at") == NOT_A_WARM_TICK.isoformat()
