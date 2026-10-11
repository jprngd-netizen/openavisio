"""Document provenance for FExEO clinical records (R4 Fase 3)

Additive: adds ``document_reference_id`` (nullable, FK ``document_references.id``,
indexed) to the records the ``POST /documents/{id}/verify`` FExEO router
materializes — ``pregnancy_visits``, ``nursing_care``, ``newborn_records`` and
``pregnancy_outcomes`` — so a re-verify retracts only what *this* document
created (soft-delete by provenance), never another document's data.

Mirrors the ``document_reference_id`` provenance already carried by
``observations`` / ``conditions`` / ``medications`` / ``recommendations`` — the
same soft-delete-then-recreate pattern, now extended to the obstetric records.

Every column is **nullable**, so existing rows and the read/create/update
contract are never broken — a record charted by hand simply carries no provenance.

Nothing existing is dropped or rewritten.

Revision ID: e4f5a6b7c8d9
Revises: b7c8d9e0f1a2
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e4f5a6b7c8d9"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


# (table, index name) — one indexed, nullable FK column each.
_TABLES = (
    ("pregnancy_visits", "ix_pregnancy_visits_document_reference_id"),
    ("nursing_care", "ix_nursing_care_document_reference_id"),
    ("newborn_records", "ix_newborn_records_document_reference_id"),
    ("pregnancy_outcomes", "ix_pregnancy_outcomes_document_reference_id"),
)


def upgrade() -> None:
    for table, index_name in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "document_reference_id",
                UUID(as_uuid=True),
                sa.ForeignKey("document_references.id"),
                nullable=True,
            ),
        )
        op.create_index(index_name, table, ["document_reference_id"])


def downgrade() -> None:
    for table, index_name in reversed(_TABLES):
        op.drop_index(index_name, table_name=table)
        op.drop_column(table, "document_reference_id")
