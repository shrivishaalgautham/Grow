import sqlalchemy as sa

from alembic import op

revision = "0003_google_sso"
down_revision = "0002_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])


def downgrade() -> None:
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "email")
