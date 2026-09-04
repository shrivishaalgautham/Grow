import pytest
from sqlalchemy import func, select

from app.jobs import store
from app.jobs.daily import compute_baselines
from app.models import PeerCluster
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
