"""obstetric episode resource — pregnancies (OB-1)

Additive: creates the ``pregnancies`` table (one row per gestation episode).
Anchors the prenatal visits (``PregnancyVisit``, OB-2) and the outcome (OB-3).
No ``gravida``/``para`` columns on ``patients`` — the GOP is derived from these
episodes (OB-DEC-1).

Dates are typed pure ``Date`` (WS-5 convention). ``estimated_due_date`` is the
Naegele DPP (LMP + 280 days); ``ultrasound_due_date`` is the optional early-USG
correction that prevails over it (OB-RSK-1).

Revision ID: b2c3d4e5f6a7
Revises: a9b8c7d6e5f4
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "b2c3d4e5f6a7"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pregnancies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("lmp_date", sa.Date(), nullable=True),
        sa.Column("estimated_due_date", sa.Date(), nullable=True),
        sa.Column("ultrasound_due_date", sa.Date(), nullable=True),
        sa.Column("ultrasound_date", sa.Date(), nullable=True),
        sa.Column("ended_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("patient_id", "lmp_date", name="uq_pregnancies_patient_lmp"),
    )
    op.create_index("ix_pregnancies_patient_id", "pregnancies", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_pregnancies_patient_id", table_name="pregnancies")
    op.drop_table("pregnancies")
