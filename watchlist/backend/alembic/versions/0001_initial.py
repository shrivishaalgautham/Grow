import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "symbols",
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=80), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=32), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "baselines",
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("beta", sa.Float(), nullable=False),
        sa.Column("residual_sigma", sa.Float(), nullable=False),
        sa.Column("raw_mean_20", sa.Float(), nullable=False),
        sa.Column("raw_sigma_20", sa.Float(), nullable=False),
        sa.Column("sigma_daily_90", sa.Float(), nullable=False),
        sa.Column("avg_volume_20d", sa.Float(), nullable=False),
        sa.Column("sma_20", sa.Float(), nullable=False),
        sa.Column("sma_50", sa.Float(), nullable=False),
        sa.Column("sma_200", sa.Float(), nullable=False),
        sa.Column("high_52w", sa.Float(), nullable=False),
        sa.Column("low_52w", sa.Float(), nullable=False),
        sa.Column("prev_close", sa.Float(), nullable=False),
        sa.Column("prev_high", sa.Float(), nullable=False),
        sa.Column("prev_low", sa.Float(), nullable=False),
        sa.Column("cluster_id", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "briefing_cache",
        sa.Column("cache_key", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.String(length=600), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("cache_key"),
    )
    op.create_table(
        "daily_bars",
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.PrimaryKeyConstraint("symbol", "date"),
    )
    op.create_table(
        "peer_clusters",
        sa.Column("cluster_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.PrimaryKeyConstraint("cluster_id", "symbol"),
    )
    op.create_table(
        "quotes",
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("prev_close", sa.Float(), nullable=False),
        sa.Column("day_high", sa.Float(), nullable=False),
        sa.Column("day_low", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("alt_price", sa.Float(), nullable=True),
        sa.Column("alt_source", sa.String(length=16), nullable=True),
        sa.Column("alt_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("divergence_pct", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("magnitude", sa.Float(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "signal_type", "trading_date", name="uq_signal_events_symbol_type_date"
        ),
    )
    op.create_index(
        "ix_signal_events_trading_date", "signal_events", ["trading_date"], unique=False
    )
    op.create_table(
        "user_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("nl_text", sa.String(length=200), nullable=False),
        sa.Column("compiled", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preview", sa.String(length=400), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_symbol_state",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_price", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "symbol"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=24), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["symbols.symbol"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_items_user_symbol"),
    )
    op.create_index("ix_watchlist_items_symbol", "watchlist_items", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_watchlist_items_symbol", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_table("user_symbol_state")
    op.drop_table("user_rules")
    op.drop_index("ix_signal_events_trading_date", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("quotes")
    op.drop_table("peer_clusters")
    op.drop_table("daily_bars")
    op.drop_table("briefing_cache")
    op.drop_table("baselines")
    op.drop_table("users")
    op.drop_table("symbols")
