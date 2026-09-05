import pytest
from sqlalchemy import func, select

from app.jobs import store
from app.jobs.daily import _rsi_crossing, _sma_crossover, compute_baselines
from app.models import PeerCluster, SignalEvent
from tests.jobs.conftest import CORRELATED, INDEPENDENT, SYMBOLS, insert_bars, insert_symbols


@pytest.fixture
def seeded(session, universe_bars):
    insert_symbols(session)
    insert_bars(session, universe_bars)


def cluster_computed_at(session):
    return session.execute(select(func.max(PeerCluster.computed_at))).scalar_one()


def test_writes_a_baseline_per_symbol_and_clusters_the_correlated_group(session, seeded):
    count = compute_baselines()

    baselines = store.load_baselines(session)
    assert count == len(SYMBOLS)
    assert set(baselines) == set(SYMBOLS)
    correlated_ids = {baselines[symbol].cluster_id for symbol in CORRELATED}
    assert len(correlated_ids) == 1
    assert None not in correlated_ids
    assert all(baselines[symbol].cluster_id is None for symbol in INDEPENDENT)
    assert all(row.confidence == "ok" for row in baselines.values())
    assert sorted(session.execute(select(PeerCluster.symbol)).scalars()) == CORRELATED


def test_clusters_are_reused_within_seven_days_unless_forced(session, seeded):
    compute_baselines()
    first = cluster_computed_at(session)

    compute_baselines()
    assert cluster_computed_at(session) == first

    compute_baselines(force_clusters=True)
    assert cluster_computed_at(session) > first


def test_first_baseline_computation_never_fires_crossing_events(session, seeded):
    compute_baselines()

    events = session.execute(select(func.count()).select_from(SignalEvent)).scalar_one()
    assert events == 0


class TestSmaCrossover:
    def test_golden_cross_when_twenty_day_overtakes_fifty_day(self):
        result = _sma_crossover(old_20=98.0, old_50=100.0, new_20=101.0, new_50=100.0)

        assert result == ("golden", 1.0)

    def test_death_cross_when_twenty_day_falls_below_fifty_day(self):
        result = _sma_crossover(old_20=102.0, old_50=100.0, new_20=99.0, new_50=100.0)

        assert result == ("death", 2.0)

    def test_no_event_when_ordering_is_unchanged(self):
        assert _sma_crossover(old_20=105.0, old_50=100.0, new_20=106.0, new_50=100.0) is None

    def test_no_event_without_a_prior_baseline(self):
        assert _sma_crossover(old_20=None, old_50=None, new_20=101.0, new_50=100.0) is None


class TestRsiCrossing:
    def test_crossing_into_overbought(self):
        assert _rsi_crossing(old=65.0, new=72.0) == ("overbought", 72.0)

    def test_crossing_into_oversold(self):
        assert _rsi_crossing(old=35.0, new=28.0) == ("oversold", 28.0)

    def test_no_event_while_staying_inside_the_neutral_band(self):
        assert _rsi_crossing(old=55.0, new=60.0) is None

    def test_no_event_without_a_prior_rsi(self):
        assert _rsi_crossing(old=None, new=80.0) is None
