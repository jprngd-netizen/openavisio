"""nursing-care records — dated, frozen, general + obstetric (OB-5)

Additive: creates the ``nursing_care`` table. One row per nursing-care record.

* ``occurred_at`` is a typed ``DateTime(timezone=True)`` (WS-5): the instant the
  care happened — the record's anchor. Following the "the record is a snapshot
  of its date" principle, the record is dated and frozen; nothing is derived for
  "today" and the listing orders by ``occurred_at`` (newest first), which is why
  it is indexed.
* ``category`` (``general`` | ``obstetric``) splits the approved scope; a
  controlled value, stored as ``String(20)`` with a ``general`` default.
* ``pregnancy_id`` is the nullable back-reference to the ``pregnancies`` episode
  an obstetric record may annotate, exactly as OB-4 linked vitals/exams. The
  router enforces that the episode belongs to the SAME patient (422).

Nothing existing is dropped or rewritten.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nursing_care",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="general"),
        sa.Column("pregnancy_id", UUID(as_uuid=True), sa.ForeignKey("pregnancies.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.String(length=256), nullable=True),
    )
    op.create_index("ix_nursing_care_patient_id", "nursing_care", ["patient_id"])
    op.create_index("ix_nursing_care_occurred_at", "nursing_care", ["occurred_at"])
    op.create_index("ix_nursing_care_pregnancy_id", "nursing_care", ["pregnancy_id"])


def downgrade() -> None:
    op.drop_index("ix_nursing_care_pregnancy_id", table_name="nursing_care")
    op.drop_index("ix_nursing_care_occurred_at", table_name="nursing_care")
    op.drop_index("ix_nursing_care_patient_id", table_name="nursing_care")
    op.drop_table("nursing_care")
