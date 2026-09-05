import sqlalchemy as sa

from alembic import op

revision = "0002_notifications"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("target", sa.String(length=254), nullable=False),
        sa.Column("verify_token_hash", sa.String(length=64), nullable=True),
        sa.Column("verify_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribe_token", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "kind", name="uq_notification_channels_user_kind"),
        sa.UniqueConstraint("unsubscribe_token"),
    )
    op.create_table(
        "notification_log",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["channel_id"], ["notification_channels.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("channel_id", "event_key"),
    )


def downgrade() -> None:
    op.drop_table("notification_log")
    op.drop_table("notification_channels")
