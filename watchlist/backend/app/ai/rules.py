import json
import logging
import re
from collections.abc import Sequence

from pydantic import ValidationError

from app.ai import client
from app.ai.prompts import RULES_SYSTEM, untrusted
from app.engine.rules_eval import render_plain_english
from app.schemas import Rule, RuleCompileOut

log = logging.getLogger(__name__)

MAX_TOKENS = 200
MAX_ERROR_CHARS = 200
CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)")
VOLUME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:x|×|times)\b")
DOWN_WORDS = re.compile(r"\b(drop|drops|fall|falls|down|below|lose|loses|decline)\b")
DEFAULT_RESIDUAL_PCT = 1.5
GENERIC_NAME_WORDS = {"ltd", "ltd.", "limited", "india", "the", "&", "and", "of"}


def compile_rule(text: str, universe: Sequence[tuple[str, str]]) -> RuleCompileOut:
    symbols = [symbol for symbol, _ in universe]
    compiled = _compile_with_llm(text, universe)
    if compiled is None:
        compiled = _compile_heuristically(text, universe)
    if isinstance(compiled, str):
        return RuleCompileOut(rule=None, preview=None, error=compiled[:MAX_ERROR_CHARS])
    if compiled.symbols != "all":
        unknown = [s for s in compiled.symbols if s not in symbols]
        if unknown:
            return RuleCompileOut(
                rule=None, preview=None, error=f"Unknown symbol: {', '.join(unknown)}"
            )
    return RuleCompileOut(rule=compiled, preview=render_plain_english(compiled), error=None)


def _compile_with_llm(text: str, universe: Sequence[tuple[str, str]]) -> Rule | str | None:
    listing = "\n".join(f"{symbol} ({name})" for symbol, name in universe)
    prompt = f"Universe:\n{listing}\n\nRequest: {untrusted(text)}"
    completion = client.complete("rules", RULES_SYSTEM, prompt, MAX_TOKENS)
    if completion is None:
        return None
    return parse_compiled(completion.text)


def parse_compiled(raw: str) -> Rule | str:
    try:
        payload = json.loads(CODE_FENCE_RE.sub("", raw.strip()))
    except json.JSONDecodeError:
        return "The assistant did not return a rule. Try rephrasing with a number."
    if not isinstance(payload, dict):
        return "The assistant did not return a rule. Try rephrasing with a number."
    if "error" in payload:
        return str(payload["error"])[:MAX_ERROR_CHARS]
    try:
        return Rule.model_validate(payload)
    except ValidationError as exc:
        log.info("rule rejected reason=%s", exc.errors()[0].get("msg", "invalid"))
        return "The compiled rule used a field or value outside the allowed set."


def _compile_heuristically(text: str, universe: Sequence[tuple[str, str]]) -> Rule | str:
    lowered = text.lower()
    conditions: list[dict] = []
    percent = PERCENT_RE.search(lowered)
    volume = VOLUME_RE.search(lowered)
    is_down = DOWN_WORDS.search(lowered) is not None
    if percent:
        value = float(percent.group(1))
        if is_down:
            conditions.append({"field": "residual_pct", "op": "<=", "value": -value})
        else:
            conditions.append({"field": "abs_residual_pct", "op": ">=", "value": value})
    if volume:
        conditions.append({"field": "rvol", "op": ">=", "value": float(volume.group(1))})
    if "52" in lowered and "high" in lowered:
        conditions.append({"field": "level_break", "op": "==", "value": "52w_high"})
    elif "52" in lowered and "low" in lowered:
        conditions.append({"field": "level_break", "op": "==", "value": "52w_low"})
    if "no catalyst" in lowered or "unexplained" in lowered:
        conditions.append({"field": "has_catalyst", "op": "==", "value": False})
    if "without" in lowered and ("peer" in lowered or "sector" in lowered):
        conditions.append({"field": "abs_peer_return_pct", "op": "<=", "value": 0.5})
        if not percent:
            conditions.insert(
                0, {"field": "abs_residual_pct", "op": ">=", "value": DEFAULT_RESIDUAL_PCT}
            )
    if not conditions:
        return (
            "Could not find a threshold. Name a percentage, a volume multiple, or a 52-week level."
        )
    named = _named_symbols(lowered, universe)
    try:
        return Rule.model_validate({"symbols": named or "all", "all": conditions})
    except ValidationError:
        return "That rule would match everything; add a threshold above zero."


def _named_symbols(lowered: str, universe: Sequence[tuple[str, str]]) -> list[str]:
    found = []
    for symbol, name in universe:
        base = symbol.split(".")[0].lower()
        if _mentions(lowered, base) or _mentions_name(lowered, name):
            found.append(symbol)
    return found[:20]


def _mentions_name(lowered: str, name: str) -> bool:
    words = [w for w in name.lower().split() if w not in GENERIC_NAME_WORDS][:2]
    return bool(words) and len(words[0]) > 3 and all(_mentions(lowered, w) for w in words)


def _mentions(lowered: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", lowered) is not None
