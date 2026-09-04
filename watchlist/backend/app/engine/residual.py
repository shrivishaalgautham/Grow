from dataclasses import dataclass
from typing import Literal

from app.engine.baselines import Baseline

Z_CAP = 20.0


@dataclass(frozen=True)
class Decomposition:
    today_change_pct: float
    peer_change_pct: float
    residual_pct: float
    z_score: float
    raw_z_score: float
    peer_method: Literal["cluster", "beta"]


def decompose(
    price: float,
    prev_close: float,
    index_return: float,
    peer_return: float | None,
    b: Baseline,
) -> Decomposition:
    if prev_close <= 0:
        raise ValueError(f"prev_close must be positive, got {prev_close}")
    today_return = price / prev_close - 1
    if peer_return is not None:
        peer_change, method = peer_return, "cluster"
    else:
        peer_change, method = b.beta * index_return, "beta"
    residual = today_return - peer_change
    return Decomposition(
        today_change_pct=today_return * 100,
        peer_change_pct=peer_change * 100,
        residual_pct=residual * 100,
        z_score=_capped_z(residual, b.residual_sigma),
        raw_z_score=_capped_z(today_return - b.raw_mean_20, b.raw_sigma_20),
        peer_method=method,
    )


def _capped_z(deviation: float, sigma: float) -> float:
    if sigma <= 0:
        return 0.0
    return min(abs(deviation) / sigma, Z_CAP)
