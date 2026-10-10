"""structured immunizations + family history by kinship (WS-7)

Additive: creates the ``immunizations`` (FHIR ``Immunization``-like) and
``family_history`` (one row per relative/condition) tables. The legacy
free-text ``clinical_histories.family_history`` column is deliberately left
intact (non-used legacy) — dropping it is a later cleanup stage.

Revision ID: c4f5a6b7d8e9
Revises: c3e4f5a6b7d8
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c4f5a6b7d8e9"
down_revision = "c3e4f5a6b7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "immunizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("vaccine_code", sa.String(length=100), nullable=True),
        sa.Column("vaccine_display", sa.String(length=256), nullable=False),
        sa.Column("dose_number", sa.Integer(), nullable=True),
        sa.Column("occurrence_date", sa.Date(), nullable=True),
        sa.Column("lot_number", sa.String(length=100), nullable=True),
        sa.Column("route", sa.String(length=100), nullable=True),
        sa.Column("site", sa.String(length=100), nullable=True),
        sa.Column("manufacturer", sa.String(length=256), nullable=True),
        sa.Column("reaction", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_immunizations_patient_id", "immunizations", ["patient_id"])

    op.create_table(
        "family_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("relationship", sa.String(length=30), nullable=False),
        sa.Column("condition_code", sa.String(length=100), nullable=True),
        sa.Column("condition_display", sa.String(length=256), nullable=False),
        sa.Column("age_at_onset", sa.Integer(), nullable=True),
        sa.Column("deceased", sa.Boolean(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_family_history_patient_id", "family_history", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_family_history_patient_id", table_name="family_history")
    op.drop_table("family_history")
    op.drop_index("ix_immunizations_patient_id", table_name="immunizations")
    op.drop_table("immunizations")
