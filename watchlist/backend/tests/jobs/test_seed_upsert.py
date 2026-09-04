import json
import time

import httpx
import respx
from sqlalchemy import func, select

from app.cache import cache
from app.jobs.daily import fetch_history, main
from app.models import Baseline, DailyBar, Quote, SignalEvent, Symbol
from tests.jobs.conftest import (
    SESSIONS,
    SYMBOLS,
    chart_history_payload,
    insert_bars,
    insert_symbols,
    yahoo_route,
)


def bar_count(session) -> int:
    return session.execute(select(func.count()).select_from(DailyBar)).scalar_one()


def symbols_with_bars(session) -> set[str]:
    return set(session.execute(select(DailyBar.symbol).distinct()).scalars())


def history_response(frame) -> httpx.Response:
    return httpx.Response(200, json=chart_history_payload(frame))


@respx.mock
def test_fetch_history_twice_yields_the_same_bar_count(session, universe_bars):
    insert_symbols(session, ["A.NS", "B.NS"])
    for symbol in ("A.NS", "B.NS"):
        yahoo_route(symbol).mock(return_value=history_response(universe_bars[symbol]))

    fetch_history(["A.NS", "B.NS"], "1y")
    first = bar_count(session)
    fetch_history(["A.NS", "B.NS"], "1y")

    assert first == 2 * SESSIONS
    assert bar_count(session) == first


@respx.mock
def test_404_symbol_is_skipped_and_the_run_continues(session, universe_bars):
    insert_symbols(session, ["A.NS", "B.NS"])
    yahoo_route("A.NS").mock(
        return_value=httpx.Response(404, json={"chart": {"result": None, "error": {}}})
    )
    yahoo_route("B.NS").mock(return_value=history_response(universe_bars["B.NS"]))

    counts = fetch_history(["A.NS", "B.NS"], "1y")

    assert counts == {"ok": 1, "skipped": 1}
    assert symbols_with_bars(session) == {"B.NS"}


@respx.mock
def test_429_then_200_succeeds_after_backoff(session, universe_bars, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    insert_symbols(session, ["A.NS"])
    yahoo_route("A.NS").mock(
        side_effect=[httpx.Response(429), history_response(universe_bars["A.NS"])]
    )

    counts = fetch_history(["A.NS"], "1y")

    assert counts == {"ok": 1, "skipped": 0}
    assert bar_count(session) == SESSIONS
    assert len(sleeps) == 1
    assert 1.0 <= sleeps[0] < 2.0


@respx.mock
def test_persistent_429_is_skipped_after_three_retries(session, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    insert_symbols(session, ["A.NS"])
    route = yahoo_route("A.NS").mock(return_value=httpx.Response(429))

    counts = fetch_history(["A.NS"], "1y")

    assert counts == {"ok": 0, "skipped": 1}
    assert route.call_count == 4
    assert [int(delay) for delay in sleeps] == [1, 2, 4]
    assert bar_count(session) == 0


def test_seed_cli_with_skip_fetch_runs_every_step(session, universe_bars):
    insert_symbols(session)
    insert_bars(session, universe_bars)

    main(["--seed", "--skip-fetch", "--backfill-sessions", "30"])

    assert session.get(Symbol, "^NSEI").is_active is False
    assert session.execute(select(func.count()).select_from(Symbol)).scalar_one() > 150
    assert set(session.execute(select(Baseline.symbol)).scalars()) == set(SYMBOLS)
    assert session.execute(select(func.count()).select_from(SignalEvent)).scalar_one() > 0
    assert set(session.execute(select(Quote.symbol)).scalars()) == {*SYMBOLS, "^NSEI"}
    cached = json.loads(cache.get("q:A.NS"))
    assert cached["confidence"] == "closed"
    assert cached["price"] == session.get(Quote, "A.NS").price
