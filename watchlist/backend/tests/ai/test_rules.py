import json

import pytest

from app.ai import rules
from app.ai.client import Completion
from app.schemas import Rule

UNIVERSE = [
    ("RELIANCE.NS", "Reliance Industries"),
    ("TCS.NS", "Tata Consultancy Services"),
    ("TMPV.NS", "Tata Motors Passenger Vehicles"),
    ("MARUTI.NS", "Maruti Suzuki India"),
]


@pytest.mark.parametrize(
    "payload",
    [
        {"symbols": "all", "all": [{"field": "z_score", "op": ">=", "value": "NaN"}]},
        {"symbols": "all", "all": [{"field": "rvol", "op": ">=", "value": "Infinity"}]},
        {"symbols": "all", "all": [{"field": "rvol", "op": ">=", "value": 1.5}] * 11},
        {"symbols": "all", "all": [{"field": "price", "op": ">=", "value": 100}]},
        {"symbols": "all", "all": [{"field": "z_score", "op": ">=", "value": -100}]},
        {"symbols": ["X.NS"] * 21, "all": [{"field": "rvol", "op": ">=", "value": 2}]},
        {"symbols": "all", "all": [{"field": "level_break", "op": ">=", "value": "52w_high"}]},
    ],
)
def test_out_of_bounds_rules_are_rejected_not_coerced(payload):
    compiled = rules.parse_compiled(json.dumps(payload))

    assert isinstance(compiled, str)
    assert "allowed set" in compiled


def test_llm_error_object_is_surfaced_as_the_error():
    compiled = rules.parse_compiled('{"error": "Zomato is not in the universe."}')

    assert compiled == "Zomato is not in the universe."


def test_fenced_json_is_parsed_and_rendered(monkeypatch):
    monkeypatch.setattr(
        rules.client,
        "complete",
        lambda *args: Completion(
            '```json\n{"symbols": ["TMPV.NS"], "all": ['
            '{"field": "abs_residual_pct", "op": ">=", "value": 1.5},'
            '{"field": "abs_peer_return_pct", "op": "<=", "value": 0.5}]}\n```',
            "m",
        ),
    )

    out = rules.compile_rule("tell me when Tata Motors moves without the auto sector", UNIVERSE)

    assert out.error is None
    assert out.rule == Rule.model_validate(
        {
            "symbols": ["TMPV.NS"],
            "all": [
                {"field": "abs_residual_pct", "op": ">=", "value": 1.5},
                {"field": "abs_peer_return_pct", "op": "<=", "value": 0.5},
            ],
        }
    )
    assert out.preview == (
        "Alert on TMPV when its stock-specific move is at least 1.5% "
        "and its peer group moves no more than 0.5%."
    )


def test_symbols_outside_the_universe_are_rejected_even_when_well_formed(monkeypatch):
    monkeypatch.setattr(
        rules.client,
        "complete",
        lambda *args: Completion(
            '{"symbols": ["ZOMATO.NS"], "all": [{"field": "rvol", "op": ">=", "value": 2}]}', "m"
        ),
    )

    out = rules.compile_rule("zomato on double volume", UNIVERSE)

    assert out.rule is None
    assert out.error == "Unknown symbol: ZOMATO.NS"


def test_heuristic_fallback_compiles_percent_volume_and_names_without_a_model(monkeypatch):
    monkeypatch.setattr(rules.client, "complete", lambda *args: None)

    out = rules.compile_rule("alert when Reliance drops 2% against peers on 3x volume", UNIVERSE)

    assert out.error is None
    assert out.rule.symbols == ["RELIANCE.NS"]
    assert [c.model_dump() for c in out.rule.all] == [
        {"field": "residual_pct", "op": "<=", "value": -2.0},
        {"field": "rvol", "op": ">=", "value": 3.0},
    ]


def test_heuristic_fallback_maps_a_two_word_company_name_without_sibling_matches(monkeypatch):
    monkeypatch.setattr(rules.client, "complete", lambda *args: None)

    out = rules.compile_rule("tata motors moves 2% without the auto sector", UNIVERSE)

    assert out.rule.symbols == ["TMPV.NS"]
    assert [c.field for c in out.rule.all] == ["abs_residual_pct", "abs_peer_return_pct"]


def test_heuristic_fallback_without_any_threshold_returns_an_error(monkeypatch):
    monkeypatch.setattr(rules.client, "complete", lambda *args: None)

    out = rules.compile_rule("tell me when something interesting happens", UNIVERSE)

    assert out.rule is None
    assert out.error.startswith("Could not find a threshold")
