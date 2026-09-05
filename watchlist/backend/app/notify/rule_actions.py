import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.deps import ApiError
from app.engine.digest import build_digest
from app.models import NotificationChannel, RuleActionLog, User, UserRule
from app.notify import email, webhook
from app.notify.compose import rule_alert_message
from app.notify.dispatch import event_key
from app.schemas import Item, Signal

log = logging.getLogger(__name__)


def run(now: datetime) -> int:
    fired = 0
    with db.SessionLocal() as session:
        rules = session.scalars(
            select(UserRule).where(UserRule.enabled.is_(True), UserRule.actions != [])
        ).all()
        by_user: dict[uuid.UUID, list[UserRule]] = {}
        for rule in rules:
            by_user.setdefault(rule.user_id, []).append(rule)
        for user_id, user_rules in by_user.items():
            fired += _process_user(session, user_id, user_rules, now)
        session.commit()
    if rules:
        log.info("rule_actions users=%d rules=%d fired=%d", len(by_user), len(rules), fired)
    return fired


def _process_user(
    session: Session, user_id: uuid.UUID, user_rules: list[UserRule], now: datetime
) -> int:
    user = session.get(User, user_id)
    if user is None:
        return 0
    try:
        digest = build_digest(session, user, now)
    except ApiError:
        return 0
    by_rule_id = {str(rule.id): rule for rule in user_rules}
    fired = 0
    for item in digest.items:
        for signal in item.signals:
            rule = by_rule_id.get(signal.rule_id or "")
            if rule is None:
                continue
            key = event_key(item, signal)
            if session.get(RuleActionLog, (rule.id, key)) is not None:
                continue
            _fire(session, user, rule, item, signal)
            session.add(RuleActionLog(rule_id=rule.id, event_key=key, sent_at=now))
            fired += 1
    return fired


def _fire(session: Session, user: User, rule: UserRule, item: Item, signal: Signal) -> None:
    for action in rule.actions:
        if action["type"] == "email":
            _fire_email(session, user, rule, item, signal)
        elif action["type"] == "webhook":
            webhook.send(action["url"], action["secret"], _webhook_payload(rule, item, signal))


def _fire_email(session: Session, user: User, rule: UserRule, item: Item, signal: Signal) -> None:
    channel = session.scalar(
        select(NotificationChannel).where(
            NotificationChannel.user_id == user.id,
            NotificationChannel.kind == "email",
            NotificationChannel.verified_at.is_not(None),
            NotificationChannel.enabled.is_(True),
        )
    )
    if channel is None:
        return
    subject, text = rule_alert_message(rule.preview, item, signal, channel.unsubscribe_token)
    email.send(email.Message(to=channel.target, subject=subject, text=text))


def _webhook_payload(rule: UserRule, item: Item, signal: Signal) -> dict:
    return {
        "rule_id": str(rule.id),
        "rule": rule.preview,
        "symbol": item.symbol,
        "signal_type": signal.type,
        "headline": signal.headline,
        "detail": signal.detail,
        "price": item.quote.price,
        "fired_at": signal.fired_at.isoformat(),
    }
