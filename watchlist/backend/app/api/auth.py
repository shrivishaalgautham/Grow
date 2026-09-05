import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import clock
from app.api.ratelimit import global_ip_limit
from app.api.sample import sample_display_name, seed_sample_watchlist
from app.db import get_session
from app.deps import current_session, current_user, rate_limit
from app.models import AuthSession, User
from app.schemas import MeOut, SessionCreate, SessionOut, UserOut

SESSION_DAYS = 30

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(global_ip_limit)])


@router.post(
    "/session",
    status_code=201,
    response_model=SessionOut,
    dependencies=[Depends(rate_limit("session", 10, 3600, per="ip"))],
)
def create_session(payload: SessionCreate, session: Session = Depends(get_session)) -> SessionOut:
    now = clock.now()
    generated = payload.start_with_sample or payload.display_name is None
    user = User(display_name=sample_display_name() if generated else payload.display_name)
    session.add(user)
    session.flush()
    if payload.start_with_sample:
        seed_sample_watchlist(session, user, now)
    token, auth = issue_session(session, user, now)
    session.commit()
    return SessionOut(token=token, expires_at=auth.expires_at, user=_user_out(user))


@router.get("/me", response_model=MeOut)
def me(auth: AuthSession = Depends(current_session)) -> MeOut:
    user = auth.user
    return MeOut(
        id=str(user.id),
        display_name=user.display_name,
        is_sample=user.is_sample,
        email=user.email,
        last_reviewed_at=user.last_reviewed_at,
        expires_at=auth.expires_at,
    )


@router.delete("/session", status_code=204)
def delete_session(
    auth: AuthSession = Depends(current_session), session: Session = Depends(get_session)
) -> Response:
    session.delete(auth)
    session.commit()
    return Response(status_code=204)


@router.delete("/account", status_code=204)
def delete_account(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> Response:
    session.delete(user)
    session.commit()
    return Response(status_code=204)


def _user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), display_name=user.display_name, is_sample=user.is_sample)


def issue_session(session: Session, user: User, now: datetime) -> tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    auth = AuthSession(
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        user_id=user.id,
        expires_at=now + timedelta(days=SESSION_DAYS),
    )
    session.add(auth)
    return token, auth
