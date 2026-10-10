"""vital-sign component group for paired readings (WS-4)

Blood pressure is a panel made of two components — systolic and diastolic
captured at the same instant. Both are stored as Observation rows; this adds a
nullable, indexed ``component_group_id`` so the two rows of one reading share a
group and can be read back (and charted) as a single measurement.

The column is additive and nullable; existing rows are unaffected. The legacy
``panel`` String column is unrelated (it holds the lab report section) and is
deliberately NOT reused for this.

Revision ID: a1c2o3m4p5g6
Revises: z7v8w9x0y1z2
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "a1c2o3m4p5g6"
down_revision = "z7v8w9x0y1z2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("component_group_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_observations_component_group_id", "observations", ["component_group_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_observations_component_group_id", table_name="observations")
    op.drop_column("observations", "component_group_id")
