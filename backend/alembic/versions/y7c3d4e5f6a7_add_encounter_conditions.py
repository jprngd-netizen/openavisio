"""encounter_conditions: N diagnoses per consultation → problem list (WS-3)

Additive: creates the ``encounter_conditions`` association table (mirrors
``condition_sources``) that links a consultation to the canonical Condition it
diagnosed. The single legacy ``encounters.cid10_code``/``cid10_display`` columns
are deliberately left intact (deprecated) — dropping them is a later cleanup.

Backfill is conservative and idempotent: every non-deleted consultation with a
legacy ``cid10_code`` is linked to the patient's Condition for that code — reused
when one already exists, created otherwise. Conditions are never duplicated and
the downgrade keeps them (they are problem-list entries now); only the links go.

Revision ID: y7c3d4e5f6a7
Revises: x6b2c3d4e5f6
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.services.encounter_diagnoses import backfill_encounter_diagnoses

revision = "y7c3d4e5f6a7"
down_revision = "x6b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encounter_conditions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("condition_id", UUID(as_uuid=True), sa.ForeignKey("conditions.id"), nullable=False),
        sa.Column("cid10_code", sa.String(length=20), nullable=True),
        sa.Column("cid10_display", sa.String(length=256), nullable=True),
        sa.UniqueConstraint("encounter_id", "condition_id", name="uq_encounter_conditions_encounter_condition"),
    )
    op.create_index("ix_encounter_conditions_encounter_id", "encounter_conditions", ["encounter_id"])
    op.create_index("ix_encounter_conditions_condition_id", "encounter_conditions", ["condition_id"])

    # Link the legacy single-CID consultations to their Condition.
    backfill_encounter_diagnoses(op.get_bind())


def downgrade() -> None:
    # Only the association goes. The Conditions created by the backfill stay —
    # they are problem-list entries now, and deleting clinical data is never the
    # safe rollback.
    op.drop_index("ix_encounter_conditions_condition_id", table_name="encounter_conditions")
    op.drop_index("ix_encounter_conditions_encounter_id", table_name="encounter_conditions")
    op.drop_table("encounter_conditions")
