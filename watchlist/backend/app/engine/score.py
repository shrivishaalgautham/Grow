from collections.abc import Sequence
from typing import Literal

RVOL_MULTIPLIER_START = 1.5
Z_SCORE_CAP = 6.0
HIGH_ATTENTION_SCORE = 3.0


def volume_multiplier(rvol: float) -> float:
    if rvol < RVOL_MULTIPLIER_START:
        return 1.0
    return 1.0 + min(rvol - RVOL_MULTIPLIER_START, 2.0) / 2.0


def level_bonus(breaks: Sequence[str]) -> float:
    if any(name.startswith("52w_") for name in breaks):
        return 1.0
    if any(name.startswith("prev_") for name in breaks):
        return 0.5
    return 0.0


def score(z_score: float, rvol: float, breaks: Sequence[str]) -> float:
    return min(z_score, Z_SCORE_CAP) * volume_multiplier(rvol) + level_bonus(breaks)


def attention(score_value: float, fired_any: bool) -> Literal["high", "notable", "quiet"]:
    if score_value >= HIGH_ATTENTION_SCORE:
        return "high"
    if fired_any:
        return "notable"
    return "quiet"
