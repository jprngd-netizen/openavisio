"""prenatal visits — pregnancy_visits (OB-2)

Additive: creates the ``pregnancy_visits`` table. A prenatal consultation is a
dedicated resource linked to its ``Pregnancy`` episode (**OB-DEC-2**) — not an
``Encounter`` — because its obstetric fields (fundal height, fetal heart rate,
presentation, edema, proteinuria) only make sense next to the episode.

The record is a snapshot of its date: ``visit_date`` anchors the record and the
gestational age shown for a visit is derived for that date (``as_of``), never for
"today". ``(pregnancy_id, visit_date)`` is unique — a same-day duplicate is a
data-entry error. PA/weight stay in the vitals/Observation source of truth.

Revision ID: f8b9c0d1e2f3
Revises: b2c3d4e5f6a7
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "f8b9c0d1e2f3"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pregnancy_visits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "pregnancy_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pregnancies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("fundal_height_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("fetal_heart_rate_bpm", sa.Integer(), nullable=True),
        sa.Column("presentation", sa.String(length=30), nullable=True),
        sa.Column("edema", sa.String(length=20), nullable=True),
        sa.Column("proteinuria", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "pregnancy_id", "visit_date", name="uq_pregnancy_visits_pregnancy_date"
        ),
    )
    op.create_index("ix_pregnancy_visits_pregnancy_id", "pregnancy_visits", ["pregnancy_id"])
    op.create_index("ix_pregnancy_visits_visit_date", "pregnancy_visits", ["visit_date"])


def downgrade() -> None:
    op.drop_index("ix_pregnancy_visits_visit_date", table_name="pregnancy_visits")
    op.drop_index("ix_pregnancy_visits_pregnancy_id", table_name="pregnancy_visits")
    op.drop_table("pregnancy_visits")
