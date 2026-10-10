"""encounter links — prescription/exam back-reference (WS-8)

Additive: adds the nullable ``prescriptions.encounter_id`` and
``document_references.encounter_id`` FKs so a prescription and an exam (the
exam/report is a ``DocumentReference``; its analytes are its Observation rows)
can be attributed to the consultation in which they were made/interpreted.

Revision ID: e7f8a9b0c1d2
Revises: d6f7a8b9c0d1
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e7f8a9b0c1d2"
down_revision = "d6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column("encounter_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_prescriptions_encounter_id_encounters",
        "prescriptions",
        "encounters",
        ["encounter_id"],
        ["id"],
    )
    op.create_index("ix_prescriptions_encounter_id", "prescriptions", ["encounter_id"])

    op.add_column(
        "document_references",
        sa.Column("encounter_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_references_encounter_id_encounters",
        "document_references",
        "encounters",
        ["encounter_id"],
        ["id"],
    )
    op.create_index(
        "ix_document_references_encounter_id", "document_references", ["encounter_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_document_references_encounter_id", table_name="document_references")
    op.drop_constraint(
        "fk_document_references_encounter_id_encounters",
        "document_references",
        type_="foreignkey",
    )
    op.drop_column("document_references", "encounter_id")

    op.drop_index("ix_prescriptions_encounter_id", table_name="prescriptions")
    op.drop_constraint(
        "fk_prescriptions_encounter_id_encounters", "prescriptions", type_="foreignkey"
    )
    op.drop_column("prescriptions", "encounter_id")
