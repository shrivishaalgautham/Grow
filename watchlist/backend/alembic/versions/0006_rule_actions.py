import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_rule_actions"
down_revision = "0005_baseline_rsi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_rules",
        sa.Column(
            "actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_table(
        "rule_action_log",
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["user_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id", "event_key"),
    )


def downgrade() -> None:
    op.drop_table("rule_action_log")
    op.drop_column("user_rules", "actions")
