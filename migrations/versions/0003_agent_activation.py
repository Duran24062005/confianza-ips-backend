"""Replace the shared Waylo credential with patient activation codes."""

import sqlalchemy as sa
from alembic import op

revision = "0003_agent_activation"
down_revision = "0002_waylo_auth_attempts"
branch_labels = None
depends_on = None


def _index_names(bind: sa.Connection, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agent_activation_codes" not in tables:
        op.create_table(
            "agent_activation_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
            sa.Column("code_digest", sa.String(length=64), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "issued_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
        )
    if "ix_agent_activation_patient_expiry" not in _index_names(bind, "agent_activation_codes"):
        op.create_index(
            "ix_agent_activation_patient_expiry",
            "agent_activation_codes",
            ["patient_id", "expires_at"],
        )
    if "uq_agent_activation_active_patient" not in _index_names(bind, "agent_activation_codes"):
        op.create_index(
            "uq_agent_activation_active_patient",
            "agent_activation_codes",
            ["patient_id"],
            unique=True,
            postgresql_where=sa.text("consumed_at IS NULL AND revoked_at IS NULL"),
            sqlite_where=sa.text("consumed_at IS NULL AND revoked_at IS NULL"),
        )

    if "waylo_auth_attempts" in tables and "agent_auth_attempts" not in tables:
        op.rename_table("waylo_auth_attempts", "agent_auth_attempts")
        op.alter_column(
            "agent_auth_attempts",
            "email_fingerprint",
            new_column_name="document_fingerprint",
        )
        op.add_column(
            "agent_auth_attempts",
            sa.Column("eps_fingerprint", sa.String(length=64), nullable=False, server_default=""),
        )
        op.add_column(
            "agent_auth_attempts",
            sa.Column(
                "client_fingerprint", sa.String(length=64), nullable=False, server_default=""
            ),
        )
        indexes = _index_names(bind, "agent_auth_attempts")
        if "ix_waylo_auth_attempts_email_time" in indexes:
            op.drop_index("ix_waylo_auth_attempts_email_time", table_name="agent_auth_attempts")
        if "ix_waylo_auth_attempts_ip_time" in indexes:
            op.drop_index("ix_waylo_auth_attempts_ip_time", table_name="agent_auth_attempts")
    elif "waylo_auth_attempts" in tables and "agent_auth_attempts" in tables:
        op.execute(
            sa.text(
                "INSERT INTO agent_auth_attempts "
                "(document_fingerprint, eps_fingerprint, ip_fingerprint, client_fingerprint, "
                "attempted_at, succeeded) "
                "SELECT email_fingerprint, '', ip_fingerprint, '', attempted_at, succeeded "
                "FROM waylo_auth_attempts"
            )
        )
        for index in ("ix_waylo_auth_attempts_email_time", "ix_waylo_auth_attempts_ip_time"):
            if index in _index_names(bind, "waylo_auth_attempts"):
                op.drop_index(index, table_name="waylo_auth_attempts")
        op.drop_table("waylo_auth_attempts")
    elif "agent_auth_attempts" not in tables:
        op.create_table(
            "agent_auth_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("document_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("eps_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("ip_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("client_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("succeeded", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    indexes = _index_names(bind, "agent_auth_attempts")
    if "ix_agent_auth_attempts_document_time" not in indexes:
        op.create_index(
            "ix_agent_auth_attempts_document_time",
            "agent_auth_attempts",
            ["document_fingerprint", "attempted_at"],
        )
    if "ix_agent_auth_attempts_ip_time" not in indexes:
        op.create_index(
            "ix_agent_auth_attempts_ip_time",
            "agent_auth_attempts",
            ["ip_fingerprint", "attempted_at"],
        )
    if "ix_agent_auth_attempts_client_time" not in indexes:
        op.create_index(
            "ix_agent_auth_attempts_client_time",
            "agent_auth_attempts",
            ["client_fingerprint", "attempted_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_activation_codes" in tables:
        if "uq_agent_activation_active_patient" in _index_names(bind, "agent_activation_codes"):
            op.drop_index(
                "uq_agent_activation_active_patient", table_name="agent_activation_codes"
            )
        if "ix_agent_activation_patient_expiry" in _index_names(bind, "agent_activation_codes"):
            op.drop_index(
                "ix_agent_activation_patient_expiry", table_name="agent_activation_codes"
            )
        op.drop_table("agent_activation_codes")
    if "agent_auth_attempts" in tables:
        for index in (
            "ix_agent_auth_attempts_client_time",
            "ix_agent_auth_attempts_ip_time",
            "ix_agent_auth_attempts_document_time",
        ):
            if index in _index_names(bind, "agent_auth_attempts"):
                op.drop_index(index, table_name="agent_auth_attempts")
        op.drop_table("agent_auth_attempts")
