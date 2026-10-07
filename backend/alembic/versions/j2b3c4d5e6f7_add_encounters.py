"""add encounters table

Prontuário consultation/evolution records: one row per clinical encounter,
carrying the SOAP-style narrative blocks plus an optional CID-10 coding.

Revision ID: j2b3c4d5e6f7
Revises: i1a2b3c4d5e6
Create Date: 2026-10-07

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "j2b3c4d5e6f7"
down_revision = "i1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encounters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="finished"),
        sa.Column("encounter_type", sa.String(50), nullable=True),
        sa.Column("encounter_date", sa.String(50), nullable=True),
        sa.Column("chief_complaint", sa.Text(), nullable=True),
        sa.Column("history", sa.Text(), nullable=True),
        sa.Column("physical_exam", sa.Text(), nullable=True),
        sa.Column("assessment", sa.Text(), nullable=True),
        sa.Column("plan", sa.Text(), nullable=True),
        sa.Column("cid10_code", sa.String(20), nullable=True),
        sa.Column("cid10_display", sa.String(256), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_encounters_patient_id", "encounters", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_encounters_patient_id", table_name="encounters")
    op.drop_table("encounters")