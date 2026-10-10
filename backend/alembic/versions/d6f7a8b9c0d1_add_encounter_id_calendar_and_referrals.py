"""consultation follow-up link + referrals (WS-10)

Additive: adds the nullable ``calendar_events.encounter_id`` FK (so a return
appointment scheduled from a consultation is linked back to it) and creates the
``referrals`` table (encaminhamento issued from a consultation).

Revision ID: d6f7a8b9c0d1
Revises: c4f5a6b7d8e9
Create Date: 2026-10-10

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "d6f7a8b9c0d1"
down_revision = "c4f5a6b7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column("encounter_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_calendar_events_encounter_id_encounters",
        "calendar_events",
        "encounters",
        ["encounter_id"],
        ["id"],
    )
    op.create_index("ix_calendar_events_encounter_id", "calendar_events", ["encounter_id"])

    op.create_table(
        "referrals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=True),
        sa.Column("target_specialty", sa.String(length=256), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_referrals_patient_id", "referrals", ["patient_id"])
    op.create_index("ix_referrals_encounter_id", "referrals", ["encounter_id"])


def downgrade() -> None:
    op.drop_index("ix_referrals_encounter_id", table_name="referrals")
    op.drop_index("ix_referrals_patient_id", table_name="referrals")
    op.drop_table("referrals")
    op.drop_index("ix_calendar_events_encounter_id", table_name="calendar_events")
    op.drop_constraint("fk_calendar_events_encounter_id_encounters", "calendar_events", type_="foreignkey")
    op.drop_column("calendar_events", "encounter_id")
