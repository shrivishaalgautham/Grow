from app.engine.levels import level_breaks
from tests.synthetic import make_baseline


def test_52w_high_break_suppresses_same_direction_prev_high():
    baseline = make_baseline(high_52w=110.0, prev_high=105.0)

    assert level_breaks(111.0, day_high=111.0, day_low=108.0, b=baseline) == ["52w_high"]


def test_prev_day_break_fires_when_52w_holds():
    baseline = make_baseline(high_52w=120.0, prev_high=105.0, prev_low=98.0)

    assert level_breaks(106.0, day_high=106.0, day_low=97.0, b=baseline) == [
        "prev_high",
        "prev_low",
    ]


def test_none_levels_are_skipped():
    baseline = make_baseline(high_52w=None, low_52w=None, prev_high=105.0)

    assert level_breaks(200.0, day_high=200.0, day_low=99.0, b=baseline) == ["prev_high"]


def test_no_breaks_inside_the_range():
    assert level_breaks(100.0, day_high=101.0, day_low=99.0, b=make_baseline()) == []
