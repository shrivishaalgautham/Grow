import secrets
import uuid

from fastapi import APIRouter, Depends, Response
from pydantic import TypeAdapter
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import clock
from app.ai.rules import compile_rule
from app.api.ratelimit import global_ip_limit, llm_global_daily, llm_user_limits
from app.db import get_session
from app.deps import ApiError, current_user
from app.engine.digest import build_digest
from app.engine.rules_eval import render_plain_english
from app.models import Symbol, User, UserRule
from app.schemas import Rule, RuleAction, RuleCompileIn, RuleCompileOut, RuleCreateIn, RuleListItem, RuleOut

MAX_RULES_PER_USER = 10
_ACTIONS_ADAPTER = TypeAdapter(list[RuleAction])

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(global_ip_limit)])


@router.post(
    "/compile",
    response_model=RuleCompileOut,
    dependencies=[*(Depends(limit) for limit in llm_user_limits), Depends(llm_global_daily)],
)
def compile_text(
    payload: RuleCompileIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RuleCompileOut:
    return compile_rule(payload.text, _universe(session))


@router.post("", status_code=201, response_model=RuleOut)
def create_rule(
    payload: RuleCreateIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RuleOut:
    _require_known_symbols(session, payload.rule)
    count = session.execute(
        select(func.count()).select_from(UserRule).where(UserRule.user_id == user.id)
    ).scalar_one()
    if count >= MAX_RULES_PER_USER:
        raise ApiError(400, "invalid_rule", f"at most {MAX_RULES_PER_USER} rules per user")
    row = UserRule(
        user_id=user.id,
        nl_text=payload.nl_text,
        compiled=payload.rule.model_dump(),
        preview=render_plain_english(payload.rule),
        actions=[_prepare_action(action).model_dump() for action in payload.actions],
        created_at=clock.now(),
    )
    session.add(row)
    session.commit()
    return _rule_out(row)


@router.get("", response_model=list[RuleListItem])
def list_rules(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[RuleListItem]:
    rows = session.scalars(
        select(UserRule).where(UserRule.user_id == user.id).order_by(UserRule.created_at)
    ).all()
    matched = _matched_today(session, user) if rows else {}
    return [
        RuleListItem(
            id=str(row.id),
            nl_text=row.nl_text,
            preview=row.preview,
            actions=_ACTIONS_ADAPTER.validate_python(row.actions),
            enabled=row.enabled,
            created_at=row.created_at,
            matched_today=sorted(matched.get(str(row.id), set())),
        )
        for row in rows
    ]


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    try:
        parsed = uuid.UUID(rule_id)
    except ValueError:
        raise ApiError(404, "invalid_request", "unknown rule") from None
    session.execute(delete(UserRule).where(UserRule.id == parsed, UserRule.user_id == user.id))
    session.commit()
    return Response(status_code=204)


def _universe(session: Session) -> list[tuple[str, str]]:
    rows = session.execute(
        select(Symbol.symbol, Symbol.name).where(Symbol.is_active.is_(True)).order_by(Symbol.symbol)
    )
    return [(symbol, name) for symbol, name in rows]


def _require_known_symbols(session: Session, rule: Rule) -> None:
    if rule.symbols == "all":
        return
    known = set(
        session.scalars(
            select(Symbol.symbol).where(Symbol.symbol.in_(rule.symbols), Symbol.is_active.is_(True))
        )
    )
    unknown = [s for s in rule.symbols if s not in known]
    if unknown:
        raise ApiError(400, "not_in_universe", f"unknown symbols: {', '.join(unknown)}")


def _matched_today(session: Session, user: User) -> dict[str, set[str]]:
    try:
        digest = build_digest(session, user, clock.now())
    except ApiError:
        return {}
    matched: dict[str, set[str]] = {}
    for item in digest.items:
        for signal in item.signals:
            if signal.rule_id is not None:
                matched.setdefault(signal.rule_id, set()).add(item.symbol)
    return matched


def _prepare_action(action: RuleAction) -> RuleAction:
    if action.type == "webhook":
        return action.model_copy(update={"secret": secrets.token_urlsafe(32)})
    return action


def _rule_out(row: UserRule) -> RuleOut:
    return RuleOut(
        id=str(row.id),
        nl_text=row.nl_text,
        rule=Rule.model_validate(row.compiled),
        preview=row.preview,
        actions=_ACTIONS_ADAPTER.validate_python(row.actions),
        enabled=row.enabled,
        created_at=row.created_at,
    )
