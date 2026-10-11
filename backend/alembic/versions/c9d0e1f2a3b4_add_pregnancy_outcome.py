"""pregnancy outcome — pregnancy_outcomes (OB-3)

Additive: creates the ``pregnancy_outcomes`` table. The outcome is the dated,
frozen record that *closes* a ``Pregnancy`` episode — a separate 1:1 table
(unique on ``pregnancy_id``) rather than columns embedded in ``pregnancies``,
so "at most one outcome per gestation" is a database invariant and the episode
either has an outcome (closed) or does not (open).

The record carries the complete outcome taxonomy (**OB-DEC-3**): term delivery
(vaginal/cesarean), miscarriage, induced abortion, ectopic, fetal death. Newborn
data (weight / APGAR 1' & 5' / sex) is only meaningful for a live birth and stays
NULL for losses. Following the "record is a snapshot of its date" principle, the
gestational age at the outcome is *derived* for ``outcome_date`` and never
stored — so there is no column for it here.

Revision ID: c9d0e1f2a3b4
Revises: f8b9c0d1e2f3
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c9d0e1f2a3b4"
down_revision = "f8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pregnancy_outcomes",
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
        sa.Column("outcome_type", sa.String(length=30), nullable=False),
        sa.Column("outcome_date", sa.Date(), nullable=False),
        sa.Column("newborn_weight_g", sa.Integer(), nullable=True),
        sa.Column("apgar_1", sa.Integer(), nullable=True),
        sa.Column("apgar_5", sa.Integer(), nullable=True),
        sa.Column("newborn_sex", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("pregnancy_id", name="uq_pregnancy_outcomes_pregnancy"),
    )
    op.create_index(
        "ix_pregnancy_outcomes_pregnancy_id", "pregnancy_outcomes", ["pregnancy_id"]
    )
    op.create_index("ix_pregnancy_outcomes_outcome_date", "pregnancy_outcomes", ["outcome_date"])


def downgrade() -> None:
    op.drop_index("ix_pregnancy_outcomes_outcome_date", table_name="pregnancy_outcomes")
    op.drop_index("ix_pregnancy_outcomes_pregnancy_id", table_name="pregnancy_outcomes")
    op.drop_table("pregnancy_outcomes")
