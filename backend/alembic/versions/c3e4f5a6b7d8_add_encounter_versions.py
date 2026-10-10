"""author + immutable seal/version of a consultation note (WS-6)

Additive:
* ``encounters.prescriber_id`` — nullable FK to the Prescriber singleton, the
  professional responsible for the note (board fields live on the Prescriber);
* ``encounter_versions`` — append-only table holding each signed version of a
  note: the content snapshot (JSONB), its deterministic SHA-256 ``content_hash``,
  when/who signed it, and a self-sufficient snapshot of the professional's
  council fields as they stood at seal time.

Nothing existing is altered beyond the new nullable column, so a rollback is a
plain revert. No backfill: historical notes simply have no seal until signed.

Revision ID: c3e4f5a6b7d8
Revises: a1c2o3m4p5g6
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "c3e4f5a6b7d8"
down_revision = "a1c2o3m4p5g6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "encounters",
        sa.Column("prescriber_id", UUID(as_uuid=True), sa.ForeignKey("prescribers.id"), nullable=True),
    )
    op.create_index("ix_encounters_prescriber_id", "encounters", ["prescriber_id"])

    op.create_table(
        "encounter_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("professional_name", sa.String(length=240), nullable=True),
        sa.Column("board_code", sa.String(length=10), nullable=True),
        sa.Column("board_number", sa.String(length=30), nullable=True),
        sa.Column("board_state", sa.String(length=2), nullable=True),
        sa.UniqueConstraint("encounter_id", "version", name="uq_encounter_versions_encounter_version"),
    )
    op.create_index("ix_encounter_versions_encounter_id", "encounter_versions", ["encounter_id"])
    op.create_index("ix_encounter_versions_signed_by", "encounter_versions", ["signed_by"])


def downgrade() -> None:
    op.drop_index("ix_encounter_versions_signed_by", table_name="encounter_versions")
    op.drop_index("ix_encounter_versions_encounter_id", table_name="encounter_versions")
    op.drop_table("encounter_versions")
    op.drop_index("ix_encounters_prescriber_id", table_name="encounters")
    op.drop_column("encounters", "prescriber_id")
