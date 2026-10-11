"""NursingCare FExEO subcategory + new newborn_records table (R4 Fase 1)

Additive: adds the FExEO-SUS structured fields to ``nursing_care``
(``subcategory`` / ``instrument_type`` / ``structured_data``) and creates the
``newborn_records`` table (1:1 with ``pregnancy_outcomes``) holding the newborn
data of instrumentos I.2/I.3.

Every new ``nursing_care`` column is **nullable** so existing rows and the
public read/create/update contract are never broken — the data simply reads back
``None`` until charted. The newborn table is new; every clinical column is
nullable so a record may be opened with only the outcome link and filled in
progressively.

The caderno is a *schema source*: only clinical data of the newborn is modeled
(never the especializanda/preceptora, which is formative and out of scope). The
subcategory is validated by a bounded ``StrEnum`` at the ORM/schema layer; the
structured sub-objects are ``JSONB`` (the repo's JSON convention).

Nothing existing is dropped or rewritten.

Revision ID: b7c8d9e0f1a2
Revises: f3a4b5c6d7e8
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "b7c8d9e0f1a2"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


_NURSING_CARE_COLUMNS = (
    sa.Column("subcategory", sa.String(length=30), nullable=True),
    sa.Column("instrument_type", sa.String(length=120), nullable=True),
    sa.Column("structured_data", JSONB(), nullable=True),
)


def upgrade() -> None:
    for column in _NURSING_CARE_COLUMNS:
        op.add_column("nursing_care", column)

    op.create_table(
        "newborn_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "pregnancy_outcome_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pregnancy_outcomes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("birth_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sex", sa.String(length=20), nullable=True),
        sa.Column("delivery_type", sa.String(length=30), nullable=True),
        sa.Column("gestational_age_weeks", sa.Numeric(4, 1), nullable=True),
        sa.Column("classification", sa.String(length=10), nullable=True),
        sa.Column("apgar_1", sa.Integer(), nullable=True),
        sa.Column("apgar_5", sa.Integer(), nullable=True),
        sa.Column("apgar_10", sa.Integer(), nullable=True),
        sa.Column("weight_g", sa.Integer(), nullable=True),
        sa.Column("length_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("pc_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("pt_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("pa_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("physical_exam", JSONB(), nullable=True),
        sa.Column("reflexes", JSONB(), nullable=True),
        sa.Column("feeding", sa.String(length=256), nullable=True),
        sa.Column("eliminations", JSONB(), nullable=True),
        sa.Column("hypoglycemia", sa.Boolean(), nullable=True),
        sa.Column("hypothermia", sa.Boolean(), nullable=True),
        sa.Column("immunization", JSONB(), nullable=True),
        sa.Column("congenital_malformation", JSONB(), nullable=True),
        sa.Column("reanimation", JSONB(), nullable=True),
        sa.Column("skin_to_skin_1h", sa.Boolean(), nullable=True),
        sa.Column("cord_clamping", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("pregnancy_outcome_id", name="uq_newborn_records_pregnancy_outcome"),
    )
    op.create_index(
        "ix_newborn_records_pregnancy_outcome_id", "newborn_records", ["pregnancy_outcome_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_newborn_records_pregnancy_outcome_id", table_name="newborn_records")
    op.drop_table("newborn_records")
    for column in reversed(_NURSING_CARE_COLUMNS):
        op.drop_column("nursing_care", column.name)
