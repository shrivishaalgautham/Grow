import pytest

from app.engine.score import attention, level_bonus, score, volume_multiplier


def test_volume_confirmed_z3_outranks_unconfirmed_z5():
    assert score(3.0, 3.0, []) == pytest.approx(5.25)
    assert score(3.0, 3.0, []) > score(5.0, 1.0, [])


def test_saturated_volume_at_z3_outranks_unconfirmed_z5_with_prev_break():
    assert score(3.0, 3.5, []) == pytest.approx(6.0)
    assert score(3.0, 3.5, []) > score(5.0, 1.0, ["prev_high"])


def test_volume_multiplier_starts_at_1_5_and_saturates():
    assert volume_multiplier(1.49) == 1.0
    assert volume_multiplier(1.5) == 1.0
    assert volume_multiplier(2.5) == 1.5
    assert volume_multiplier(3.5) == 2.0
    assert volume_multiplier(10.0) == 2.0


def test_level_bonus_prefers_52w_over_prev_day():
    assert level_bonus(["52w_high", "prev_low"]) == 1.0
    assert level_bonus(["prev_low"]) == 0.5
    assert level_bonus([]) == 0.0


def test_z_is_capped_at_six():
    assert score(20.0, 1.0, []) == pytest.approx(6.0)


@pytest.mark.parametrize(
    ("score_value", "fired_any", "expected"),
    [
        (3.0, False, "high"),
        (2.99, True, "notable"),
        (2.99, False, "quiet"),
        (0.0, True, "notable"),
    ],
)
def test_attention_tiers_at_boundaries(score_value, fired_any, expected):
    assert attention(score_value, fired_any) == expected
