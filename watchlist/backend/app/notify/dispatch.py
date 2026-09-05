import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.config import settings
from app.deps import ApiError
from app.engine.digest import build_digest
from app.models import NotificationChannel, NotificationLog, User
from app.notify import email
from app.notify.compose import alert_message
from app.schemas import Item, Signal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchSummary:
    channels: int
    sent: int
    skipped_gap: int
    skipped_quiet: int


def dispatch(now: datetime) -> DispatchSummary:
    sent = skipped_gap = skipped_quiet = 0
    with db.SessionLocal() as session:
        channels = list(
            session.scalars(
                select(NotificationChannel).where(
                    NotificationChannel.verified_at.is_not(None),
                    NotificationChannel.enabled.is_(True),
                )
            )
        )
        for channel in channels:
            if _within_gap(channel, now):
                skipped_gap += 1
                continue
            fresh = _fresh_signals(session, channel, now)
            if not fresh:
                skipped_quiet += 1
                continue
            _deliver(session, channel, fresh, now)
            sent += 1
    summary = DispatchSummary(len(channels), sent, skipped_gap, skipped_quiet)
    if channels:
        log.info(
            "notify channels=%d sent=%d skipped_gap=%d skipped_quiet=%d",
            summary.channels,
            summary.sent,
            summary.skipped_gap,
            summary.skipped_quiet,
        )
    return summary


def event_key(item: Item, signal: Signal) -> str:
    return f"{item.symbol}:{signal.type}:{signal.trading_date.isoformat()}:{signal.rule_id or ''}"


def _within_gap(channel: NotificationChannel, now: datetime) -> bool:
    if channel.last_notified_at is None:
        return False
    return now - channel.last_notified_at < timedelta(seconds=settings.notify_min_gap_seconds)


def _fresh_signals(
    session: Session, channel: NotificationChannel, now: datetime
) -> list[tuple[Item, list[Signal]]]:
    user = session.get(User, channel.user_id)
    if user is None:
        return []
    try:
        digest = build_digest(session, user, now)
    except ApiError as exc:
        log.warning("notify channel=%s skipped=%s", channel.id, exc.code)
        return []
    candidates = {
        event_key(item, signal): (item, signal)
        for item in digest.items
        if item.is_changed
        for signal in item.signals
    }
    if not candidates:
        return []
    already = set(
        session.scalars(
            select(NotificationLog.event_key).where(
                NotificationLog.channel_id == channel.id,
                NotificationLog.event_key.in_(candidates),
            )
        )
    )
    fresh: dict[str, tuple[Item, list[Signal]]] = {}
    for key, (item, signal) in candidates.items():
        if key in already:
            continue
        fresh.setdefault(item.symbol, (item, []))[1].append(signal)
    return list(fresh.values())


def _deliver(
    session: Session,
    channel: NotificationChannel,
    fresh: list[tuple[Item, list[Signal]]],
    now: datetime,
) -> None:
    subject, text = alert_message(fresh, now, channel.unsubscribe_token)
    email.send(email.Message(to=channel.target, subject=subject, text=text))
    session.add_all(
        NotificationLog(channel_id=channel.id, event_key=event_key(item, signal), sent_at=now)
        for item, signals in fresh
        for signal in signals
    )
    channel.last_notified_at = now
    session.commit()


def main(argv: list[str] | None = None) -> None:
    import argparse
    import logging

    from app import clock

    parser = argparse.ArgumentParser(prog="python -m app.notify.dispatch")
    parser.add_argument(
        "--ignore-gap",
        action="store_true",
        help="send even if the last email to the address was less than the minimum gap ago",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.ignore_gap:
        settings.notify_min_gap_seconds = 0
    print(dispatch(clock.now()))


if __name__ == "__main__":
    main()
