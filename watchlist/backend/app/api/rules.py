import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import clock
from app.ai.rules import compile_rule, unknown_symbols
from app.api.ratelimit import global_ip_limit, llm_budget
from app.db import get_session
from app.deps import ApiError, current_user
from app.engine.digest import build_digest
from app.engine.rules_eval import render_plain_english
from app.models import User, UserRule
from app.schemas import (
    DigestOut,
    RuleCompileIn,
    RuleCompileOut,
    RuleCreateIn,
    RuleListItem,
    RuleOut,
)

MAX_RULES_PER_USER = 10

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(global_ip_limit)])


@router.post("/compile", response_model=RuleCompileOut, dependencies=[Depends(llm_budget)])
def compile_text(payload: RuleCompileIn, session: Session = Depends(get_session)) -> RuleCompileOut:
    return compile_rule(session, payload.text)


@router.post("", status_code=201, response_model=RuleOut)
def create_rule(
    payload: RuleCreateIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> RuleOut:
    unknown = unknown_symbols(session, payload.rule.symbols)
    if unknown:
        raise ApiError(400, "invalid_rule", f"unknown symbols: {', '.join(unknown)}")
    if _rule_count(session, user) >= MAX_RULES_PER_USER:
        raise ApiError(400, "invalid_rule", f"at most {MAX_RULES_PER_USER} rules per user")
    row = UserRule(
        user_id=user.id,
        nl_text=payload.nl_text,
        compiled=payload.rule.model_dump(),
        preview=render_plain_english(payload.rule),
        created_at=clock.now(),
    )
    session.add(row)
    session.commit()
    return RuleOut(
        id=str(row.id),
        nl_text=row.nl_text,
        rule=payload.rule,
        preview=row.preview,
        enabled=row.enabled,
        created_at=row.created_at,
    )


@router.get("", response_model=list[RuleListItem])
def list_rules(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[RuleListItem]:
    rows = session.scalars(
        select(UserRule).where(UserRule.user_id == user.id).order_by(UserRule.created_at)
    )
    matched = _matched_today(build_digest(session, user, clock.now()))
    return [
        RuleListItem(
            id=str(row.id),
            nl_text=row.nl_text,
            preview=row.preview,
            enabled=row.enabled,
            created_at=row.created_at,
            matched_today=matched.get(str(row.id), []),
        )
        for row in rows
    ]


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    session.execute(delete(UserRule).where(UserRule.id == rule_id, UserRule.user_id == user.id))
    session.commit()
    return Response(status_code=204)


def _rule_count(session: Session, user: User) -> int:
    return session.scalar(
        select(func.count()).select_from(UserRule).where(UserRule.user_id == user.id)
    )


def _matched_today(digest: DigestOut) -> dict[str, list[str]]:
    matched: dict[str, list[str]] = {}
    for item in digest.items:
        for signal in item.signals:
            if signal.rule_id is not None:
                matched.setdefault(signal.rule_id, []).append(item.symbol)
    return matched
