"""link measurements (observations) to the encounter they were taken in

Vitals captured during a consultation are stored as Observation rows with
category="measurement" and a nullable encounter_id pointing back at the
encounter. This keeps a single source of truth: the measurements history and
the encounter record read the same rows.

Revision ID: k3c4d5e6f7a8
Revises: j2b3c4d5e6f7
Create Date: 2026-10-07

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "k3c4d5e6f7a8"
down_revision = "j2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=True),
    )
    op.create_index("ix_observations_encounter_id", "observations", ["encounter_id"])


def downgrade() -> None:
    op.drop_index("ix_observations_encounter_id", table_name="observations")
    op.drop_column("observations", "encounter_id")