import json
import logging
from collections.abc import Sequence
from typing import Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client
from app.ai.prompts import rule_messages
from app.engine.rules_eval import render_plain_english
from app.models import Symbol
from app.schemas import Rule, RuleCompileOut

log = logging.getLogger(__name__)

MAX_TOKENS = 200
UNAVAILABLE = "The rule assistant is unavailable right now. Try again in a little while."
UNPARSEABLE = (
    "That request could not be turned into a rule. Name a stock and a measurable condition, "
    "such as a stock-specific move, a volume multiple or a level break."
)


def compile_rule(session: Session, text: str) -> RuleCompileOut:
    raw = client.complete(rule_messages(text), MAX_TOKENS)
    if raw is None:
        return _failure(UNAVAILABLE)
    rule = _parse(raw)
    if rule is None:
        return _failure(UNPARSEABLE)
    unknown = unknown_symbols(session, rule.symbols)
    if unknown:
        return _failure(f"Unknown symbols: {', '.join(unknown)}")
    return RuleCompileOut(rule=rule, preview=render_plain_english(rule), error=None)


def unknown_symbols(session: Session, symbols: Sequence[str] | Literal["all"]) -> list[str]:
    if symbols == "all":
        return []
    known = set(
        session.scalars(
            select(Symbol.symbol).where(Symbol.symbol.in_(symbols), Symbol.is_active.is_(True))
        )
    )
    return [symbol for symbol in symbols if symbol not in known]


def _failure(message: str) -> RuleCompileOut:
    return RuleCompileOut(rule=None, preview=None, error=message)


def _parse(raw: str) -> Rule | None:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        log.info("rule_rejected reason=no_json chars=%d", len(raw))
        return None
    try:
        payload = json.loads(raw[start : end + 1])
    except ValueError:
        log.info("rule_rejected reason=malformed_json chars=%d", len(raw))
        return None
    if not isinstance(payload, dict) or "error" in payload:
        log.info("rule_rejected reason=unsupported")
        return None
    payload["symbols"] = _normalized_symbols(payload.get("symbols"))
    try:
        return Rule.model_validate(payload)
    except ValidationError as exc:
        log.info("rule_rejected reason=%s", exc.errors()[0]["msg"])
        return None


def _normalized_symbols(value: object) -> object:
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        return value
    return [s.upper() if "." in s else f"{s.upper()}.NS" for s in value]
