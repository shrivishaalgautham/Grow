import sqlalchemy as sa

from alembic import op

revision = "0005_baseline_rsi"
down_revision = "0004_quote_open"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("baselines", sa.Column("rsi_14", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("baselines", "rsi_14")
