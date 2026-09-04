from dataclasses import dataclass

from app.engine.signals import Evaluation
from app.schemas import Rule, RuleCondition

SUBJECT_PHRASES = {
    "residual_pct": "its signed stock-specific move is",
    "abs_residual_pct": "its stock-specific move is",
    "z_score": "its stock-specific z-score is",
    "rvol": "its relative volume is",
    "peer_return_pct": "its peer group's signed move is",
    "abs_peer_return_pct": "its peer group moves",
}
OP_PHRASES = {">=": "at least", "<=": "no more than", "==": "exactly"}
UNITS = {
    "residual_pct": "%",
    "abs_residual_pct": "%",
    "z_score": "",
    "rvol": "×",
    "peer_return_pct": "%",
    "abs_peer_return_pct": "%",
}
LEVEL_PHRASES = {
    "52w_high": "it makes a new 52-week high",
    "52w_low": "it makes a new 52-week low",
    "prev_high": "it trades above yesterday's high",
    "prev_low": "it trades below yesterday's low",
}


@dataclass(frozen=True)
class RuleFacts:
    residual_pct: float
    abs_residual_pct: float
    z_score: float
    rvol: float
    peer_return_pct: float
    abs_peer_return_pct: float
    level_break: str | None
    has_catalyst: bool


def facts_from(evaluation: Evaluation, has_catalyst: bool) -> RuleFacts:
    d = evaluation.decomposition
    return RuleFacts(
        residual_pct=d.residual_pct,
        abs_residual_pct=abs(d.residual_pct),
        z_score=d.z_score,
        rvol=evaluation.rvol,
        peer_return_pct=d.peer_change_pct,
        abs_peer_return_pct=abs(d.peer_change_pct),
        level_break=evaluation.breaks[0] if evaluation.breaks else None,
        has_catalyst=has_catalyst,
    )


def matches(rule: Rule, symbol: str, facts: RuleFacts) -> bool:
    if rule.symbols != "all" and symbol not in rule.symbols:
        return False
    return all(_holds(condition, facts) for condition in rule.all)


def _holds(condition: RuleCondition, facts: RuleFacts) -> bool:
    actual = getattr(facts, condition.field)
    if condition.op == ">=":
        return actual >= condition.value
    if condition.op == "<=":
        return actual <= condition.value
    return actual == condition.value


def render_plain_english(rule: Rule) -> str:
    conditions = " and ".join(_condition_phrase(c) for c in rule.all)
    return f"Alert on {_target_phrase(rule)} when {conditions}."


def _target_phrase(rule: Rule) -> str:
    if rule.symbols == "all":
        return "any watched stock"
    names = [symbol.split(".")[0] for symbol in rule.symbols]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} or {names[-1]}"


def _condition_phrase(condition: RuleCondition) -> str:
    if condition.field == "level_break":
        return LEVEL_PHRASES[condition.value]
    if condition.field == "has_catalyst":
        return "a public catalyst is found" if condition.value else "no public catalyst is found"
    amount = f"{condition.value:g}{UNITS[condition.field]}"
    return f"{SUBJECT_PHRASES[condition.field]} {OP_PHRASES[condition.op]} {amount}"
