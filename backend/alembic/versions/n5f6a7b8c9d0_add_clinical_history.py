"""add clinical_histories (occupational record section #2 — anamnesis)

One row per patient (unique patient_id): free-text personal/family/surgical
history, allergies and habits, plus previous employments and risk-agent
exposures as JSONB lists (minimal shape). All columns nullable; the row is
created on first save, so existing patients are untouched.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "n5f6a7b8c9d0"
down_revision = "m4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clinical_histories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("personal_history", sa.Text()),
        sa.Column("family_history", sa.Text()),
        sa.Column("surgical_history", sa.Text()),
        sa.Column("allergies", sa.Text()),
        sa.Column("habits", sa.Text()),
        sa.Column("previous_employments", JSONB()),
        sa.Column("exposures", JSONB()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("patient_id", name="uq_clinical_histories_patient"),
    )
    op.create_index("ix_clinical_histories_patient_id", "clinical_histories", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_clinical_histories_patient_id", table_name="clinical_histories")
    op.drop_table("clinical_histories")
