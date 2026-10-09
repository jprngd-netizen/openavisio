"""structured allergies / intolerances (WS-1)

Additive: creates the ``allergies`` table (FHIR ``AllergyIntolerance``-like).
The legacy free-text ``clinical_histories.allergies`` column is deliberately
left intact (non-used legacy) — dropping it is a later cleanup stage.

Revision ID: x6b2c3d4e5f6
Revises: w5a1b2c3d4e5
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "x6b2c3d4e5f6"
down_revision = "w5a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allergies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("substance_code", sa.String(length=100), nullable=True),
        sa.Column("substance_display", sa.String(length=256), nullable=False),
        sa.Column("reaction", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=30), nullable=True),
        sa.Column("onset", sa.DateTime(timezone=True), nullable=True),
        sa.Column("criticality", sa.String(length=30), nullable=False, server_default="unable_to_assess"),
        sa.Column("clinical_status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_allergies_patient_id", "allergies", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_allergies_patient_id", table_name="allergies")
    op.drop_table("allergies")
