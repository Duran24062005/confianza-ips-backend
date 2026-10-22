"""Create the initial Confianza schema."""

from alembic import op
from sqlalchemy import text

from confianza_ips_backend import models  # noqa: F401
from confianza_ips_backend.db import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        op.execute(
            text(
                "ALTER TABLE appointments ADD CONSTRAINT appointments_doctor_no_overlap "
                "EXCLUDE USING gist (doctor_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
                "WHERE (status IN ('requested', 'confirmed'))"
            )
        )
        op.execute(
            text(
                "ALTER TABLE appointments ADD CONSTRAINT appointments_patient_no_overlap "
                "EXCLUDE USING gist (patient_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) "
                "WHERE (status IN ('requested', 'confirmed'))"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            text(
                "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_doctor_no_overlap"
            )
        )
        op.execute(
            text(
                "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS appointments_patient_no_overlap"
            )
        )
    Base.metadata.drop_all(bind=bind)
