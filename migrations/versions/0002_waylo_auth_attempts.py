"""Persist anonymized Waylo authentication attempts."""

import sqlalchemy as sa
from alembic import op

revision = "0002_waylo_auth_attempts"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "waylo_auth_attempts" not in table_names:
        op.create_table(
            "waylo_auth_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("ip_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("succeeded", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    index_names = {index["name"] for index in inspector.get_indexes("waylo_auth_attempts")}
    if "ix_waylo_auth_attempts_email_time" not in index_names:
        op.create_index(
            "ix_waylo_auth_attempts_email_time",
            "waylo_auth_attempts",
            ["email_fingerprint", "attempted_at"],
        )
    if "ix_waylo_auth_attempts_ip_time" not in index_names:
        op.create_index(
            "ix_waylo_auth_attempts_ip_time",
            "waylo_auth_attempts",
            ["ip_fingerprint", "attempted_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "waylo_auth_attempts" not in inspector.get_table_names():
        return

    index_names = {index["name"] for index in inspector.get_indexes("waylo_auth_attempts")}
    if "ix_waylo_auth_attempts_ip_time" in index_names:
        op.drop_index("ix_waylo_auth_attempts_ip_time", table_name="waylo_auth_attempts")
    if "ix_waylo_auth_attempts_email_time" in index_names:
        op.drop_index("ix_waylo_auth_attempts_email_time", table_name="waylo_auth_attempts")
    op.drop_table("waylo_auth_attempts")
