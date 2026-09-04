from datetime import datetime

import httpx
import respx

from app.cache import cache
from app.clock import IST
from app.jobs.refresh import refresh_tick
from tests.jobs.conftest import add_watchlist, insert_symbols, mock_quote, yahoo_route

NOW = datetime(2026, 9, 4, 11, 2, tzinfo=IST)


@respx.mock
def test_three_provider_failures_skip_the_symbol_without_http_calls(session):
    insert_symbols(session)
    add_watchlist(session, ["A.NS", "F.NS"])
    healthy = mock_quote("A.NS", price=100.0, prev_close=100.0, as_of=NOW)
    mock_quote("^NSEI", price=100.0, prev_close=100.0, as_of=NOW)
    failing = yahoo_route("F.NS").mock(return_value=httpx.Response(500))

    for _ in range(3):
        refresh_tick(NOW)

    assert failing.call_count == 3
    assert cache.get("skip:F.NS") == "1"

    summary = refresh_tick(NOW)

    assert failing.call_count == 3
    assert healthy.call_count == 4
    assert summary.skipped == 1
    assert summary.fetched == 2
