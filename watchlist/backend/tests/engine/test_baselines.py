import numpy as np
import pandas as pd
import pytest

from app.engine.baselines import compute_baseline
from tests.synthetic import bars_from_returns, trading_dates

SESSIONS = 300


@pytest.fixture
def rng():
    return np.random.default_rng(7)


def index_returns(rng, count: int) -> pd.Series:
    return pd.Series(rng.normal(0, 0.01, count), index=trading_dates(count))


def test_median_volume_resists_a_single_spike(rng):
    volume = np.full(SESSIONS, 1_000_000.0)
    volume[-1] = 30_000_000.0
    bars = bars_from_returns(rng.normal(0, 0.01, SESSIONS), volume=volume)

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    assert baseline.avg_volume_20d == 1_000_000.0


def test_beta_is_one_when_stock_tracks_index(rng):
    index = index_returns(rng, SESSIONS)
    bars = bars_from_returns(index.to_numpy() + rng.normal(0, 0.001, SESSIONS))

    baseline = compute_baseline(bars, index)

    assert baseline.beta == pytest.approx(1.0, abs=0.05)
    assert baseline.confidence == "ok"
    assert baseline.sessions == SESSIONS


def test_short_history_is_low_confidence_with_unit_beta(rng):
    short = 30
    bars = bars_from_returns(rng.normal(0, 0.01, short))

    baseline = compute_baseline(bars, index_returns(rng, short))

    assert baseline.confidence == "low"
    assert baseline.beta == 1.0


def test_smas_and_52w_are_none_without_enough_rows(rng):
    count = 100
    bars = bars_from_returns(rng.normal(0, 0.01, count))

    baseline = compute_baseline(bars, index_returns(rng, count))

    assert baseline.sma_20 is not None
    assert baseline.sma_50 is not None
    assert baseline.sma_200 is None
    assert baseline.high_52w is None
    assert baseline.low_52w is None


def test_52w_levels_come_from_highs_and_lows_not_closes(rng):
    bars = bars_from_returns(rng.normal(0, 0.01, SESSIONS), spread=0.02)

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    last_year = bars.tail(252)
    assert baseline.high_52w == last_year["high"].max()
    assert baseline.high_52w > last_year["close"].max()
    assert baseline.low_52w == last_year["low"].min()
    assert baseline.low_52w < last_year["close"].min()


def test_prev_levels_come_from_the_last_completed_bar(rng):
    bars = bars_from_returns(rng.normal(0, 0.01, SESSIONS))

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    last = bars.iloc[-1]
    assert (baseline.prev_close, baseline.prev_high, baseline.prev_low) == (
        last["close"],
        last["high"],
        last["low"],
    )


def test_peer_returns_replace_beta_adjustment_in_residual_sigma(rng):
    index = index_returns(rng, SESSIONS)
    stock = index.to_numpy() + rng.normal(0, 0.01, SESSIONS)
    bars = bars_from_returns(stock)
    peers_identical_to_stock = pd.Series(stock, index=trading_dates(SESSIONS))

    baseline = compute_baseline(bars, index, peers_identical_to_stock)

    assert baseline.residual_sigma < 1e-10
    assert baseline.confidence == "low"


def test_rsi_is_near_100_after_a_pure_uptrend(rng):
    bars = bars_from_returns(np.full(SESSIONS, 0.01))

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    assert baseline.rsi_14 == pytest.approx(100.0, abs=0.5)


def test_rsi_is_near_zero_after_a_pure_downtrend(rng):
    bars = bars_from_returns(np.full(SESSIONS, -0.01))

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    assert baseline.rsi_14 == pytest.approx(0.0, abs=0.5)


def test_rsi_is_fifty_when_gains_and_losses_are_balanced(rng):
    bars = bars_from_returns(np.tile([0.01, -0.01], SESSIONS // 2))

    baseline = compute_baseline(bars, index_returns(rng, SESSIONS))

    assert baseline.rsi_14 == pytest.approx(50.0, abs=3.0)


def test_rsi_is_none_with_fewer_than_fifteen_sessions(rng):
    bars = bars_from_returns(np.full(10, 0.01))

    baseline = compute_baseline(bars, index_returns(rng, 10))

    assert baseline.rsi_14 is None
