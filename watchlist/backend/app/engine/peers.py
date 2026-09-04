import math
from collections.abc import Mapping, Sequence
from statistics import median

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

MIN_CLUSTER_SIZE = 4
MIN_PEERS = 3
MIN_ROWS = 60
MAX_NAN_FRACTION = 0.10


def cluster_symbols(
    returns: pd.DataFrame, distance_threshold: float = 0.6
) -> dict[str, str | None]:
    if len(returns) < MIN_ROWS:
        raise ValueError(f"clustering needs at least {MIN_ROWS} sessions, got {len(returns)}")
    usable = returns.loc[:, returns.isna().mean() <= MAX_NAN_FRACTION]
    assignment: dict[str, str | None] = dict.fromkeys(returns.columns)
    if usable.shape[1] < MIN_CLUSTER_SIZE:
        return assignment
    labels = AgglomerativeClustering(
        metric="precomputed",
        linkage="average",
        distance_threshold=distance_threshold,
        n_clusters=None,
    ).fit_predict(_correlation_distance(usable))
    for cluster_id, members in _named_clusters(list(usable.columns), labels):
        for symbol in members:
            assignment[symbol] = cluster_id
    return assignment


def _correlation_distance(returns: pd.DataFrame) -> np.ndarray:
    distance = 1.0 - returns.corr().to_numpy()
    distance = np.nan_to_num(distance, nan=1.0).clip(0.0, 2.0)
    np.fill_diagonal(distance, 0.0)
    return distance


def _named_clusters(symbols: list[str], labels: np.ndarray) -> list[tuple[str, list[str]]]:
    groups: dict[int, list[str]] = {}
    for symbol, label in zip(symbols, labels, strict=True):
        groups.setdefault(int(label), []).append(symbol)
    large = [sorted(members) for members in groups.values() if len(members) >= MIN_CLUSTER_SIZE]
    large.sort(key=lambda members: (-len(members), members[0]))
    return [(f"c{rank:02d}", members) for rank, members in enumerate(large)]


def peer_return(
    returns_today: Mapping[str, float], cluster_members: Sequence[str], exclude: str
) -> float | None:
    others = [
        returns_today[symbol]
        for symbol in cluster_members
        if symbol != exclude and symbol in returns_today and math.isfinite(returns_today[symbol])
    ]
    if len(others) < MIN_PEERS:
        return None
    return float(median(others))
