import sqlalchemy as sa

from alembic import op

revision = "0004_quote_open"
down_revision = "0003_google_sso"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("open", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "open")
