from dataclasses import asdict
from datetime import UTC, datetime

import numpy as np
import pytest

from app.evidence.replay import replay
from app.schemas import EvidenceOut
from tests.synthetic import bars_from_returns, trading_dates

SESSIONS = 300
DAYS = 90
SYMBOLS = ["A.NS", "B.NS", "C.NS", "D.NS", "E.NS"]
MARKET_CRASH_DAY = SESSIONS - 40
STOCK_SPECIFIC_DAY = SESSIONS - 10


@pytest.fixture
def universe():
    rng = np.random.default_rng(11)
    market = rng.normal(0, 0.005, SESSIONS)
    market[MARKET_CRASH_DAY] = -0.03
    market[STOCK_SPECIFIC_DAY] = 0.0
    bars = {}
    for symbol in SYMBOLS:
        returns = market + rng.normal(0, 0.002, SESSIONS)
        if symbol == "A.NS":
            returns[STOCK_SPECIFIC_DAY] += 0.012
        bars[symbol] = bars_from_returns(returns)
    return bars, bars_from_returns(market)


@pytest.fixture(params=["cluster", "beta"])
def clusters(request):
    cluster_id = "c00" if request.param == "cluster" else None
    return dict.fromkeys(SYMBOLS, cluster_id)


def test_engine_catches_the_small_stock_specific_move(universe, clusters):
    bars, index_bars = universe

    result = replay(bars, index_bars, clusters, days=DAYS)

    caught = [
        row
        for row in result.caught_extra
        if row["symbol"] == "A.NS"
        and row["date"] == trading_dates(SESSIONS)[STOCK_SPECIFIC_DAY].date()
    ]
    assert len(caught) == 1
    assert caught[0]["today_change_pct"] == pytest.approx(1.2, abs=0.2)
    assert abs(caught[0]["today_change_pct"]) < 2.0
    assert caught[0]["z_score"] >= 3.0
    assert result.engine["alerts"] >= 1


def test_market_wide_crash_is_a_naive_alert_the_engine_suppresses(universe, clusters):
    bars, index_bars = universe

    result = replay(bars, index_bars, clusters, days=DAYS)

    assert result.naive_pct_2["alerts"] == len(SYMBOLS)
    assert result.suppressed["total"] == len(SYMBOLS)
    assert result.suppressed["market_wide"] == len(SYMBOLS)
    assert result.suppressed["below_floor"] == 0
    assert result.raw_z_2["alerts"] >= len(SYMBOLS)
    assert all(abs(row["today_change_pct"]) < 2.0 for row in result.caught_extra)


def test_suppression_reasons_partition_every_suppressed_alert(universe, clusters):
    bars, index_bars = universe

    result = replay(bars, index_bars, clusters, days=DAYS)

    buckets = result.suppressed
    assert (
        buckets["market_wide"] + buckets["below_floor"] + buckets["within_noise"]
        == (buckets["total"])
    )


def test_replay_covers_the_requested_window(universe, clusters):
    bars, index_bars = universe

    result = replay(bars, index_bars, clusters, days=DAYS)

    dates = trading_dates(SESSIONS)
    assert result.days == DAYS
    assert result.symbols_count == len(SYMBOLS)
    assert result.from_date == dates[SESSIONS - DAYS].date()
    assert result.to_date == dates[-1].date()


def test_replay_shape_matches_evidence_out(universe, clusters):
    bars, index_bars = universe

    result = replay(bars, index_bars, clusters, days=DAYS)

    out = EvidenceOut(**asdict(result), computed_at=datetime.now(UTC))
    assert out.naive_pct_2.alerts == result.naive_pct_2["alerts"]
    assert out.suppressed.market_wide == result.suppressed["market_wide"]
    assert len(out.caught_extra) == len(result.caught_extra)


def test_replay_without_overlapping_dates_raises(universe):
    bars, index_bars = universe
    shifted_index = index_bars.copy()
    shifted_index.index = shifted_index.index + np.timedelta64(1000, "D")

    with pytest.raises(ValueError, match="no sessions"):
        replay(bars, shifted_index, dict.fromkeys(SYMBOLS), days=DAYS)
