from typing import Literal

from app.engine.baselines import Baseline

LevelBreak = Literal["52w_high", "52w_low", "prev_high", "prev_low"]


def level_breaks(price: float, day_high: float, day_low: float, b: Baseline) -> list[LevelBreak]:
    breaks: list[LevelBreak] = []
    broke_52w_high = b.high_52w is not None and day_high > b.high_52w
    broke_52w_low = b.low_52w is not None and day_low < b.low_52w
    if broke_52w_high:
        breaks.append("52w_high")
    if broke_52w_low:
        breaks.append("52w_low")
    if not broke_52w_high and b.prev_high is not None and day_high > b.prev_high:
        breaks.append("prev_high")
    if not broke_52w_low and b.prev_low is not None and day_low < b.prev_low:
        breaks.append("prev_low")
    return breaks
