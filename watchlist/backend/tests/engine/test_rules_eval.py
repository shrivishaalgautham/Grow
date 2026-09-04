from dataclasses import replace

import pytest

from app.engine.rules_eval import RuleFacts, facts_from, matches, render_plain_english
from app.engine.signals import evaluate
from app.schemas import Rule
from tests.synthetic import make_baseline, make_facts

WORKED_EXAMPLE = Rule.model_validate(
    {
        "symbols": ["TMPV.NS"],
        "all": [
            {"field": "abs_residual_pct", "op": ">=", "value": 1.5},
            {"field": "abs_peer_return_pct", "op": "<=", "value": 0.5},
        ],
    }
)


@pytest.fixture
def stock_specific_facts() -> RuleFacts:
    return RuleFacts(
        residual_pct=-2.0,
        abs_residual_pct=2.0,
        z_score=2.5,
        rvol=1.2,
        peer_return_pct=0.3,
        abs_peer_return_pct=0.3,
        level_break=None,
        has_catalyst=False,
    )


def test_worked_example_matches_a_stock_specific_move(stock_specific_facts):
    assert matches(WORKED_EXAMPLE, "TMPV.NS", stock_specific_facts) is True


def test_worked_example_rejects_when_peers_moved_too(stock_specific_facts):
    peers_moved = replace(stock_specific_facts, peer_return_pct=-0.8, abs_peer_return_pct=0.8)

    assert matches(WORKED_EXAMPLE, "TMPV.NS", peers_moved) is False


def test_symbol_outside_the_rule_never_matches(stock_specific_facts):
    assert matches(WORKED_EXAMPLE, "RELIANCE.NS", stock_specific_facts) is False


def test_all_symbols_rule_matches_any_symbol(stock_specific_facts):
    universe_rule = Rule.model_validate(
        {"symbols": "all", "all": [{"field": "z_score", "op": ">=", "value": 2}]}
    )

    assert matches(universe_rule, "RELIANCE.NS", stock_specific_facts) is True


def test_level_break_condition_is_equality(stock_specific_facts):
    rule = Rule.model_validate(
        {"symbols": "all", "all": [{"field": "level_break", "op": "==", "value": "52w_high"}]}
    )

    assert matches(rule, "TMPV.NS", replace(stock_specific_facts, level_break="52w_high"))
    assert not matches(rule, "TMPV.NS", replace(stock_specific_facts, level_break="prev_high"))
    assert not matches(rule, "TMPV.NS", stock_specific_facts)


def test_has_catalyst_condition(stock_specific_facts):
    rule = Rule.model_validate(
        {"symbols": "all", "all": [{"field": "has_catalyst", "op": "==", "value": False}]}
    )

    assert matches(rule, "TMPV.NS", stock_specific_facts)
    assert not matches(rule, "TMPV.NS", replace(stock_specific_facts, has_catalyst=True))


def test_facts_from_evaluation_uses_the_first_break():
    baseline = make_baseline(high_52w=110.0, prev_low=98.0)
    evaluation = evaluate(
        make_facts(price=102.5, day_high=111.0, day_low=97.0, peer_return=-0.003), baseline
    )

    facts = facts_from(evaluation, has_catalyst=True)

    assert facts.level_break == "52w_high"
    assert facts.residual_pct == pytest.approx(2.8)
    assert facts.abs_residual_pct == pytest.approx(2.8)
    assert facts.peer_return_pct == pytest.approx(-0.3)
    assert facts.abs_peer_return_pct == pytest.approx(0.3)
    assert facts.z_score == pytest.approx(2.8)
    assert facts.rvol == 1.0
    assert facts.has_catalyst is True


def test_render_worked_example():
    assert render_plain_english(WORKED_EXAMPLE) == (
        "Alert on TMPV when its stock-specific move is at least 1.5%"
        " and its peer group moves no more than 0.5%."
    )


def test_render_universe_rule_with_level_and_volume():
    rule = Rule.model_validate(
        {
            "symbols": "all",
            "all": [
                {"field": "level_break", "op": "==", "value": "52w_high"},
                {"field": "rvol", "op": ">=", "value": 2},
                {"field": "has_catalyst", "op": "==", "value": False},
            ],
        }
    )

    assert render_plain_english(rule) == (
        "Alert on any watched stock when it makes a new 52-week high"
        " and its relative volume is at least 2× and no public catalyst is found."
    )


def test_render_lists_multiple_symbols():
    rule = Rule.model_validate(
        {
            "symbols": ["TMPV.NS", "RELIANCE.NS", "INFY.NS"],
            "all": [{"field": "z_score", "op": ">=", "value": 3}],
        }
    )

    assert render_plain_english(rule) == (
        "Alert on TMPV, RELIANCE or INFY when its stock-specific z-score is at least 3."
    )
