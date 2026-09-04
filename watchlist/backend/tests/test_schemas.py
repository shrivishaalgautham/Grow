import math
import re

import pytest
from pydantic import ValidationError

from app.schemas import SYMBOL_PATTERN, ItemAdd, Rule, RuleCondition, SessionCreate

WORKED_EXAMPLE = {
    "symbols": ["TMPV.NS"],
    "all": [
        {"field": "abs_residual_pct", "op": ">=", "value": 1.5},
        {"field": "abs_peer_return_pct", "op": "<=", "value": 0.5},
    ],
}


def condition(field: str, op: str, value) -> dict:
    return {"field": field, "op": op, "value": value}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Alice_01", "alice_01"), ("ＡＢＣ-ｄｅｆ", "abc-def"), ("Straße", "strasse")],
)
def test_display_name_is_nfkc_casefolded(raw, expected):
    assert SessionCreate(display_name=raw).display_name == expected


@pytest.mark.parametrize("raw", ["ab", "a" * 33, "has space", "emoji😀", "dots.here", ""])
def test_display_name_rejected(raw):
    with pytest.raises(ValidationError):
        SessionCreate(display_name=raw)


def test_display_name_optional():
    assert SessionCreate().display_name is None


@pytest.mark.parametrize("symbol", ["RELIANCE.NS", "M&M.NS", "BAJAJ-AUTO.NS", "500325.BO"])
def test_symbol_regex_accepts(symbol):
    assert ItemAdd(symbol=symbol).symbol == symbol
    assert re.fullmatch(SYMBOL_PATTERN, symbol)


@pytest.mark.parametrize(
    "symbol",
    [
        "reliance.NS",
        "RELIANCE",
        "RELIANCE.XX",
        "../etc.NS",
        "RELIANCE.NS?range=max",
        "A" * 21 + ".NS",
    ],
)
def test_symbol_regex_rejects(symbol):
    with pytest.raises(ValidationError):
        ItemAdd(symbol=symbol)


def test_rule_accepts_worked_example():
    rule = Rule.model_validate(WORKED_EXAMPLE)
    assert rule.symbols == ["TMPV.NS"]
    assert [c.field for c in rule.all] == ["abs_residual_pct", "abs_peer_return_pct"]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rule_rejects_non_finite_values(value):
    with pytest.raises(ValidationError):
        Rule(symbols=["TMPV.NS"], all=[condition("rvol", ">=", value)])


def test_rule_rejects_non_finite_json_literals():
    with pytest.raises(ValidationError):
        Rule.model_validate_json('{"symbols":"all","all":[{"field":"rvol","op":">=","value":NaN}]}')


def test_rule_rejects_eleven_conditions():
    with pytest.raises(ValidationError):
        Rule(symbols=["TMPV.NS"], all=[condition("rvol", ">=", 2)] * 11)


def test_rule_rejects_zero_conditions():
    with pytest.raises(ValidationError):
        Rule(symbols=["TMPV.NS"], all=[])


def test_rule_rejects_twenty_one_symbols():
    symbols = [f"S{i}.NS" for i in range(21)]
    with pytest.raises(ValidationError):
        Rule(symbols=symbols, all=[condition("rvol", ">=", 2)])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rvol", -1),
        ("rvol", 101),
        ("z_score", 21),
        ("z_score", -1),
        ("residual_pct", 101),
        ("abs_peer_return_pct", -101),
    ],
)
def test_rule_rejects_out_of_range_values(field, value):
    with pytest.raises(ValidationError):
        RuleCondition(field=field, op=">=", value=value)


def test_rule_rejects_unknown_field():
    with pytest.raises(ValidationError):
        RuleCondition(field="rsi", op=">=", value=70)


def test_rule_rejects_unknown_op():
    with pytest.raises(ValidationError):
        RuleCondition(field="rvol", op=">", value=2)


@pytest.mark.parametrize("value", ["2", True, None])
def test_numeric_field_rejects_non_numeric_value(value):
    with pytest.raises(ValidationError):
        RuleCondition(field="rvol", op=">=", value=value)


def test_level_break_accepts_level_names_only():
    assert RuleCondition(field="level_break", op="==", value="52w_high").value == "52w_high"
    with pytest.raises(ValidationError):
        RuleCondition(field="level_break", op="==", value="vwap")
    with pytest.raises(ValidationError):
        RuleCondition(field="level_break", op=">=", value="52w_high")


def test_has_catalyst_requires_bool():
    assert RuleCondition(field="has_catalyst", op="==", value=False).value is False
    with pytest.raises(ValidationError):
        RuleCondition(field="has_catalyst", op="==", value="true")


@pytest.mark.parametrize(
    "always_true",
    [
        condition("z_score", ">=", 0),
        condition("rvol", ">=", 0),
        condition("abs_residual_pct", ">=", -5),
        condition("abs_peer_return_pct", ">=", 0),
    ],
)
def test_rule_rejects_all_symbols_with_always_true_condition(always_true):
    with pytest.raises(ValidationError):
        Rule(symbols="all", all=[always_true, condition("rvol", ">=", 3)])


def test_always_true_condition_allowed_on_explicit_symbols():
    rule = Rule(symbols=["TMPV.NS"], all=[condition("z_score", ">=", 0)])
    assert rule.symbols == ["TMPV.NS"]


def test_rule_over_all_symbols_with_real_condition_is_valid():
    rule = Rule(symbols="all", all=[condition("z_score", ">=", 2), condition("rvol", ">=", 1.5)])
    assert rule.symbols == "all"
