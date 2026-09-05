import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import clock
from app.api.ratelimit import global_ip_limit
from app.db import get_session
from app.deps import ApiError, current_user, rate_limit
from app.models import NotificationChannel, User
from app.notify import email
from app.notify.compose import verification_message
from app.schemas import (
    EmailChannelOut,
    EmailSubscribeIn,
    NotificationsOut,
    VerifyIn,
    VerifyOut,
)

VERIFY_TTL = timedelta(hours=24)
KIND_EMAIL = "email"

router = APIRouter(
    prefix="/notifications", tags=["notifications"], dependencies=[Depends(global_ip_limit)]
)


@router.get("", response_model=NotificationsOut)
def status(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> NotificationsOut:
    channel = _email_channel(session, user)
    return NotificationsOut(email=_channel_out(channel, clock.now()) if channel else None)


@router.post(
    "/email",
    status_code=202,
    response_model=EmailChannelOut,
    dependencies=[Depends(rate_limit("notify_subscribe", 3, 3600, per="user"))],
)
def subscribe(
    payload: EmailSubscribeIn,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> EmailChannelOut:
    now = clock.now()
    token = secrets.token_urlsafe(32)
    channel = _email_channel(session, user)
    if channel is None:
        channel = NotificationChannel(
            user_id=user.id, kind=KIND_EMAIL, unsubscribe_token=secrets.token_urlsafe(32)
        )
        session.add(channel)
    channel.target = payload.email
    channel.verify_token_hash = _hash(token)
    channel.verify_expires_at = now + VERIFY_TTL
    channel.verified_at = None
    channel.enabled = True
    session.commit()
    subject, text = verification_message(payload.email, token)
    background.add_task(email.send, email.Message(to=payload.email, subject=subject, text=text))
    return _channel_out(channel, now)


@router.post("/email/verify", response_model=VerifyOut)
def verify(payload: VerifyIn, session: Session = Depends(get_session)) -> VerifyOut:
    now = clock.now()
    channel = session.scalar(
        select(NotificationChannel).where(
            NotificationChannel.verify_token_hash == _hash(payload.token)
        )
    )
    if channel is None or channel.verify_expires_at is None or channel.verify_expires_at < now:
        raise ApiError(400, "invalid_request", "verification link is invalid or has expired")
    channel.verified_at = now
    channel.verify_token_hash = None
    channel.verify_expires_at = None
    channel.enabled = True
    session.commit()
    return VerifyOut(status="verified", address_masked=email.mask(channel.target))


@router.delete("/email", status_code=204)
def unsubscribe_own(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> Response:
    session.execute(
        delete(NotificationChannel).where(
            NotificationChannel.user_id == user.id, NotificationChannel.kind == KIND_EMAIL
        )
    )
    session.commit()
    return Response(status_code=204)


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_by_link(
    token: str = Query(min_length=16, max_length=128), session: Session = Depends(get_session)
) -> HTMLResponse:
    channel = session.scalar(
        select(NotificationChannel).where(NotificationChannel.unsubscribe_token == token)
    )
    if channel is None:
        return HTMLResponse("<p>This unsubscribe link is no longer valid.</p>", status_code=404)
    channel.enabled = False
    session.commit()
    return HTMLResponse(
        f"<p>Alerts to {email.mask(channel.target)} are switched off. "
        "You can turn them back on from the watchlist page.</p>"
    )


def _email_channel(session: Session, user: User) -> NotificationChannel | None:
    return session.scalar(
        select(NotificationChannel).where(
            NotificationChannel.user_id == user.id, NotificationChannel.kind == KIND_EMAIL
        )
    )


def _channel_out(channel: NotificationChannel, now: datetime) -> EmailChannelOut:
    if not channel.enabled:
        status_ = "disabled"
    elif channel.verified_at is not None:
        status_ = "verified"
    else:
        status_ = "pending"
    return EmailChannelOut(
        address_masked=email.mask(channel.target),
        status=status_,
        verify_expires_at=channel.verify_expires_at,
        last_notified_at=channel.last_notified_at,
    )


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
