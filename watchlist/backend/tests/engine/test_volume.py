import pytest

from app.engine.volume import relative_volume

AVG = 1_000_000.0


def test_same_raw_volume_is_far_more_unusual_at_open_than_near_close():
    at_0930, _ = relative_volume(500_000, AVG, minutes_since_open=15)
    at_1520, _ = relative_volume(500_000, AVG, minutes_since_open=365)

    assert at_0930 == pytest.approx(500_000 / (AVG * 0.05))
    assert at_1520 == pytest.approx(500_000 / (AVG * 365 / 375))
    assert at_0930 > 10 * at_1520


def test_rvol_is_approximate_only_before_45_minutes():
    _, at_30 = relative_volume(500_000, AVG, minutes_since_open=30)
    _, at_45 = relative_volume(500_000, AVG, minutes_since_open=45)

    assert at_30 is True
    assert at_45 is False


def test_end_of_day_is_unscaled_and_exact():
    assert relative_volume(3_000_000, AVG, minutes_since_open=None) == (3.0, False)


def test_zero_average_volume_yields_zero():
    assert relative_volume(3_000_000, 0.0, minutes_since_open=100) == (0.0, False)
