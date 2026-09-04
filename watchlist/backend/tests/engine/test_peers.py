import numpy as np
import pandas as pd
import pytest

from app.engine.peers import cluster_symbols, peer_return
from tests.synthetic import trading_dates


def grouped_returns(sizes: list[int], rows: int = 120, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    columns = {}
    for group, size in enumerate(sizes):
        shared = rng.normal(0, 0.01, rows)
        for member in range(size):
            columns[f"G{group}M{member}.NS"] = shared + rng.normal(0, 0.005, rows)
    return pd.DataFrame(columns, index=trading_dates(rows))


def test_three_correlated_groups_form_three_clusters():
    returns = grouped_returns([6, 6, 6])

    assignment = cluster_symbols(returns)

    ids_by_group = [
        {assignment[f"G{group}M{member}.NS"] for member in range(6)} for group in range(3)
    ]
    assert all(len(ids) == 1 for ids in ids_by_group)
    assert len({ids.pop() for ids in ids_by_group}) == 3
    assert set(assignment.values()) == {"c00", "c01", "c02"}


def test_group_below_min_cluster_size_maps_to_none():
    returns = grouped_returns([6, 6, 3])

    assignment = cluster_symbols(returns)

    assert all(assignment[f"G2M{member}.NS"] is None for member in range(3))
    assert all(assignment[f"G0M{member}.NS"] is not None for member in range(6))


def test_symbols_with_too_many_gaps_are_left_unclustered():
    returns = grouped_returns([6, 6])
    returns.iloc[:20, 0] = np.nan

    assignment = cluster_symbols(returns)

    assert assignment["G0M0.NS"] is None
    assert assignment["G0M1.NS"] is not None


def test_fewer_than_sixty_rows_raises():
    with pytest.raises(ValueError, match="60"):
        cluster_symbols(grouped_returns([6, 6], rows=59))


def test_peer_return_is_median_of_other_members():
    today = {"A.NS": 0.10, "B.NS": 0.01, "C.NS": 0.02, "D.NS": 0.03}

    assert peer_return(today, ["A.NS", "B.NS", "C.NS", "D.NS"], exclude="A.NS") == 0.02


def test_peer_return_needs_three_other_members():
    today = {"A.NS": 0.10, "B.NS": 0.01, "C.NS": 0.02, "D.NS": 0.03}

    assert peer_return(today, ["A.NS", "B.NS", "C.NS"], exclude="A.NS") is None
    assert peer_return(today, ["A.NS", "B.NS", "C.NS", "MISSING.NS"], exclude="A.NS") is None
