"""pregnancy clinical integrations — intercorrências + linked vitals/exams (OB-4)

Additive. Two halves:

* ``pregnancy_conditions`` — the association table that links a gestation to the
  canonical problem-list ``Condition`` it recorded (DMG, pre-eclampsia, ...).
  Mirrors ``encounter_conditions`` (WS-3): find-or-create the Condition by
  ``(patient_id, code)``; the CID-10 snapshot is kept as it read, and un-linking
  soft-deletes only the link — the Condition is never deleted.
* ``observations.pregnancy_id`` and ``document_references.pregnancy_id`` — the
  nullable back-references that let a vital (weight/PA) and an exam (a lab
  report) be attributed to the prenatal episode, exactly as ``encounter_id`` did
  for consultations (WS-8). Nothing is dropped or rewritten.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pregnancy_conditions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pregnancy_id", UUID(as_uuid=True), sa.ForeignKey("pregnancies.id"), nullable=False),
        sa.Column("condition_id", UUID(as_uuid=True), sa.ForeignKey("conditions.id"), nullable=False),
        sa.Column("cid10_code", sa.String(length=20), nullable=True),
        sa.Column("cid10_display", sa.String(length=256), nullable=True),
        sa.UniqueConstraint("pregnancy_id", "condition_id", name="uq_pregnancy_conditions_pregnancy_condition"),
    )
    op.create_index("ix_pregnancy_conditions_pregnancy_id", "pregnancy_conditions", ["pregnancy_id"])
    op.create_index("ix_pregnancy_conditions_condition_id", "pregnancy_conditions", ["condition_id"])

    op.add_column(
        "observations",
        sa.Column("pregnancy_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_observations_pregnancy_id_pregnancies",
        "observations",
        "pregnancies",
        ["pregnancy_id"],
        ["id"],
    )
    op.create_index("ix_observations_pregnancy_id", "observations", ["pregnancy_id"])

    op.add_column(
        "document_references",
        sa.Column("pregnancy_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_references_pregnancy_id_pregnancies",
        "document_references",
        "pregnancies",
        ["pregnancy_id"],
        ["id"],
    )
    op.create_index(
        "ix_document_references_pregnancy_id", "document_references", ["pregnancy_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_references_pregnancy_id", table_name="document_references")
    op.drop_constraint(
        "fk_document_references_pregnancy_id_pregnancies",
        "document_references",
        type_="foreignkey",
    )
    op.drop_column("document_references", "pregnancy_id")

    op.drop_index("ix_observations_pregnancy_id", table_name="observations")
    op.drop_constraint(
        "fk_observations_pregnancy_id_pregnancies", "observations", type_="foreignkey"
    )
    op.drop_column("observations", "pregnancy_id")

    # Only the association goes. The Conditions created when intercorrências were
    # recorded stay — they are problem-list entries now; deleting clinical data
    # is never the safe rollback.
    op.drop_index("ix_pregnancy_conditions_condition_id", table_name="pregnancy_conditions")
    op.drop_index("ix_pregnancy_conditions_pregnancy_id", table_name="pregnancy_conditions")
    op.drop_table("pregnancy_conditions")
