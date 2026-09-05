import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(32))
    is_sample: Mapped[bool] = mapped_column(default=False)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Symbol(Base):
    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    industry: Mapped[str] = mapped_column(String(80))
    isin: Mapped[str] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(default=True)


class DailyBar(Base):
    __tablename__ = "daily_bars"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float]
    high: Mapped[float]
    low: Mapped[float]
    close: Mapped[float]
    volume: Mapped[int] = mapped_column(BigInteger)


class Baseline(Base):
    __tablename__ = "baselines"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"), primary_key=True)
    beta: Mapped[float]
    residual_sigma: Mapped[float]
    raw_mean_20: Mapped[float]
    raw_sigma_20: Mapped[float]
    sigma_daily_90: Mapped[float]
    avg_volume_20d: Mapped[float]
    sma_20: Mapped[float]
    sma_50: Mapped[float]
    sma_200: Mapped[float]
    rsi_14: Mapped[float | None]
    high_52w: Mapped[float]
    low_52w: Mapped[float]
    prev_close: Mapped[float]
    prev_high: Mapped[float]
    prev_low: Mapped[float]
    cluster_id: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[str] = mapped_column(String(16))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PeerCluster(Base):
    __tablename__ = "peer_clusters"

    cluster_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Quote(Base):
    __tablename__ = "quotes"

    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"), primary_key=True)
    price: Mapped[float]
    prev_close: Mapped[float]
    open: Mapped[float | None]
    day_high: Mapped[float]
    day_low: Mapped[float]
    volume: Mapped[int] = mapped_column(BigInteger)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(16))
    alt_price: Mapped[float | None]
    alt_source: Mapped[str | None] = mapped_column(String(16))
    alt_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    divergence_pct: Mapped[float | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SignalEvent(Base):
    __tablename__ = "signal_events"
    __table_args__ = (
        UniqueConstraint(
            "symbol", "signal_type", "trading_date", name="uq_signal_events_symbol_type_date"
        ),
        Index("ix_signal_events_trading_date", "trading_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"))
    signal_type: Mapped[str] = mapped_column(String(32))
    trading_date: Mapped[date] = mapped_column(Date)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    magnitude: Mapped[float]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_watchlist_items_user_symbol"),
        Index("ix_watchlist_items_symbol", "symbol"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserSymbolState(Base):
    __tablename__ = "user_symbol_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(ForeignKey("symbols.symbol"), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_price: Mapped[float]


class UserRule(Base):
    __tablename__ = "user_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    nl_text: Mapped[str] = mapped_column(String(200))
    compiled: Mapped[dict[str, Any]] = mapped_column(JSONB)
    preview: Mapped[str] = mapped_column(String(400))
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BriefingCache(Base):
    __tablename__ = "briefing_cache"

    cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(String(600))
    source: Mapped[str] = mapped_column(String(16))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_notification_channels_user_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="email")
    target: Mapped[str] = mapped_column(String(254))
    verify_token_hash: Mapped[str | None] = mapped_column(String(64))
    verify_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(default=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_log"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("notification_channels.id", ondelete="CASCADE"), primary_key=True
    )
    event_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
