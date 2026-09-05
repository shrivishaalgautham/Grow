from dataclasses import replace

import pytest

from app.engine.signals import evaluate, since_seen_signal
from tests.synthetic import FIRED_AT, TRADING_DATE, make_baseline, make_facts


def signal_types(evaluation) -> list[str]:
    return [signal.type for signal in evaluation.signals]


def test_absolute_floor_suppresses_a_half_percent_move_at_z4():
    quiet_stock = make_baseline(residual_sigma=0.00125)

    evaluation = evaluate(make_facts(price=100.5), quiet_stock)

    assert evaluation.decomposition.z_score == pytest.approx(4.0)
    assert "EXCESS_MOVE" not in signal_types(evaluation)


def test_excess_move_needs_both_the_floor_and_the_z_gate():
    baseline = make_baseline(residual_sigma=0.01)

    above_floor_below_z = evaluate(make_facts(price=101.0), baseline)
    both_gates = evaluate(make_facts(price=103.0), baseline)

    assert "EXCESS_MOVE" not in signal_types(above_floor_below_z)
    assert signal_types(both_gates) == ["EXCESS_MOVE"]
    assert both_gates.is_changed is True
    assert both_gates.attention == "high"


def test_raw_z_alone_never_fires_on_a_market_wide_day():
    baseline = make_baseline(beta=1.0, raw_sigma_20=0.005, residual_sigma=0.01)

    evaluation = evaluate(make_facts(price=103.0, index_return=0.03), baseline)

    assert evaluation.decomposition.raw_z_score >= 2.0
    assert evaluation.decomposition.residual_pct == pytest.approx(0.0, abs=1e-9)
    assert "EXCESS_MOVE" not in signal_types(evaluation)


def test_low_confidence_suppresses_everything():
    baseline = make_baseline(confidence="low")

    evaluation = evaluate(make_facts(price=105.0, day_high=125.0, volume=5_000_000.0), baseline)

    assert evaluation.low_confidence is True
    assert evaluation.signals == []
    assert evaluation.score == 0.0
    assert evaluation.attention == "quiet"
    assert evaluation.is_changed is False


def test_excess_move_text_carries_signed_percentages_for_the_cluster_method():
    baseline = make_baseline(raw_sigma_20=0.02)

    evaluation = evaluate(make_facts(price=102.1, peer_return=-0.003), baseline)

    (signal,) = evaluation.signals
    assert signal.type == "EXCESS_MOVE"
    assert signal.headline == "Notable stock-specific move"
    assert signal.detail == "Up 2.1% while its peer group averaged -0.3%."
    assert signal.fired_at == FIRED_AT
    assert signal.trading_date == TRADING_DATE
    assert signal.rule_id is None


def test_excess_move_text_for_the_beta_method_and_raw_z_sentence():
    baseline = make_baseline(beta=1.5, raw_sigma_20=0.005)

    evaluation = evaluate(make_facts(price=96.0, index_return=-0.004), baseline)

    (signal,) = evaluation.signals
    assert signal.headline == "Unusually large stock-specific move"
    assert signal.detail == (
        "Down 4.0% while the market moved -0.6%, beta-adjusted."
        " Also the largest daily move vs its own 20-day range."
    )


def test_volume_confirmed_text_distinguishes_intraday_approximation():
    anchored = make_facts(price=105.0, volume=3_100_000.0)
    end_of_day = evaluate(anchored, make_baseline())
    early = evaluate(replace(anchored, minutes_since_open=30), make_baseline())

    eod_signal = next(s for s in end_of_day.signals if s.type == "VOLUME_CONFIRMED")
    early_signal = next(s for s in early.signals if s.type == "VOLUME_CONFIRMED")
    assert eod_signal.headline == "3.1× normal volume"
    assert eod_signal.detail == "Versus the 20-day median."
    assert early.rvol_is_approximate is True
    assert early_signal.detail == "Adjusted for time of day."


def test_volume_and_prev_day_breaks_need_an_excess_move_or_year_level_anchor():
    baseline = make_baseline(prev_high=102.0)
    unanchored = make_facts(price=100.5, day_high=103.0, volume=3_100_000.0)

    assert evaluate(unanchored, baseline).signals == []
    assert evaluate(unanchored, baseline).breaks == ["prev_high"]
    anchored = evaluate(replace(unanchored, price=105.0), baseline)
    assert signal_types(anchored) == ["EXCESS_MOVE", "VOLUME_CONFIRMED", "LEVEL_BREAK"]


def test_level_break_emits_one_signal_per_break():
    baseline = make_baseline(high_52w=110.0, prev_low=98.0)

    evaluation = evaluate(make_facts(price=100.0, day_high=111.0, day_low=97.0), baseline)

    assert signal_types(evaluation) == ["LEVEL_BREAK", "LEVEL_BREAK"]
    assert [s.headline for s in evaluation.signals] == [
        "New 52-week high",
        "Below yesterday's low",
    ]
    assert evaluation.breaks == ["52w_high", "prev_low"]


def test_since_seen_fires_on_three_day_drift_beyond_root_t_sigma():
    signal = since_seen_signal(6.2, 0.01, 3, FIRED_AT, TRADING_DATE)

    assert signal is not None
    assert signal.type == "SINCE_SEEN_MOVE"
    assert signal.headline == "+6.2% since you last checked"
    assert signal.detail == "Larger than expected drift over 3 trading days."


def test_since_seen_ignores_the_same_drift_over_thirty_days():
    assert since_seen_signal(6.2, 0.01, 30, FIRED_AT, TRADING_DATE) is None


def test_since_seen_respects_the_absolute_floor():
    assert since_seen_signal(-1.4, 0.002, 1, FIRED_AT, TRADING_DATE) is None
    signal = since_seen_signal(-1.5, 0.002, 1, FIRED_AT, TRADING_DATE)
    assert signal is not None
    assert signal.headline == "-1.5% since you last checked"
    assert signal.detail == "Larger than expected drift over 1 trading day."


def test_since_seen_is_none_when_sigma_is_zero():
    assert since_seen_signal(6.2, 0.0, 3, FIRED_AT, TRADING_DATE) is None


def test_gap_up_at_the_open_fires_independently_of_the_closing_move():
    baseline = make_baseline(residual_sigma=0.01)

    evaluation = evaluate(make_facts(open=103.0, price=100.3), baseline)

    assert "GAP" in signal_types(evaluation)
    assert "EXCESS_MOVE" not in signal_types(evaluation)
    gap = next(s for s in evaluation.signals if s.type == "GAP")
    assert gap.headline == "Gapped up at the open"
    assert gap.detail == "Opened at 103.00, +3.0% from yesterday's close."


def test_gap_down_reports_the_down_direction():
    baseline = make_baseline(residual_sigma=0.01)

    evaluation = evaluate(make_facts(open=97.0, price=99.7), baseline)

    gap = next(s for s in evaluation.signals if s.type == "GAP")
    assert gap.headline == "Gapped down at the open"
    assert gap.detail == "Opened at 97.00, -3.0% from yesterday's close."


def test_gap_below_the_floor_is_suppressed():
    baseline = make_baseline(residual_sigma=0.01)

    evaluation = evaluate(make_facts(open=101.0, price=100.0), baseline)

    assert "GAP" not in signal_types(evaluation)
