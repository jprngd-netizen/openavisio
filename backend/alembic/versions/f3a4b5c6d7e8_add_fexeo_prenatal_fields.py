"""FExEO-SUS prenatal structured fields on pregnancies/pregnancy_visits (R4 Fase 1)

Additive: adds the structured instrument fields (FExEO-SUS / CEEO-Rede Alyne,
Instrumento I.1 — Assistência Pré-natal) to ``pregnancies`` and
``pregnancy_visits``. Every new column is **nullable** so existing rows and the
public read/create/update contracts are never broken — the data simply reads
back ``None`` until charted.

The caderno is a *schema source*: only clinical data of the patient is modeled
(never the especializanda/preceptora, which is formative and out of scope).
Free enumerations (risk classification, IMC class, consultation type, main care
provider, edema class) are stored as bounded ``String`` and validated by the
Pydantic/ORM ``StrEnum``; the multi-select lists and the directed physical exam
are ``JSONB`` (the repo's JSON convention).

Nothing existing is dropped or rewritten.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-10-11

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


_PREGNANCY_COLUMNS = (
    sa.Column("risk_classification", sa.String(length=30), nullable=True),
    sa.Column("planned_pregnancy", sa.Boolean(), nullable=True),
    sa.Column("contraceptive_at_conception", sa.String(length=256), nullable=True),
    sa.Column("gravida", sa.Integer(), nullable=True),
    sa.Column("para_vaginal", sa.Integer(), nullable=True),
    sa.Column("para_cesarean", sa.Integer(), nullable=True),
    sa.Column("abortions", sa.Integer(), nullable=True),
    sa.Column("living_children", sa.Integer(), nullable=True),
    sa.Column("preeclampsia_risk_factors", JSONB(), nullable=True),
    sa.Column("preeclampsia_moderate_risk_factors", JSONB(), nullable=True),
    sa.Column("aspirin_prophylaxis", sa.Boolean(), nullable=True),
    sa.Column("aspirin_start_week", sa.Integer(), nullable=True),
    sa.Column("imc_pre_gestational_class", sa.String(length=30), nullable=True),
    sa.Column("perinatal_mental_health_history", sa.Boolean(), nullable=True),
    sa.Column("domestic_violence_investigated", sa.Boolean(), nullable=True),
    sa.Column("family_history", JSONB(), nullable=True),
    sa.Column("reference_maternity", sa.String(length=256), nullable=True),
    sa.Column("linked_to_maternity", sa.Boolean(), nullable=True),
)

_VISIT_COLUMNS = (
    sa.Column("consultation_type", sa.String(length=20), nullable=True),
    sa.Column("first_visit_before_12w", sa.Boolean(), nullable=True),
    sa.Column("main_care_provider", sa.String(length=20), nullable=True),
    sa.Column("remote_consult", sa.Boolean(), nullable=True),
    sa.Column("dental_health_activity", sa.Boolean(), nullable=True),
    sa.Column("complaints", JSONB(), nullable=True),
    sa.Column("warning_signs", JSONB(), nullable=True),
    sa.Column("current_intercurrences", JSONB(), nullable=True),
    sa.Column("edema_class", sa.String(length=10), nullable=True),
    sa.Column("leopold_done", sa.Boolean(), nullable=True),
    sa.Column("fundal_height_recorded_on_chart", sa.Boolean(), nullable=True),
    sa.Column("bcf_change", sa.Boolean(), nullable=True),
    sa.Column("physical_exam", JSONB(), nullable=True),
    sa.Column("vaccination_status", JSONB(), nullable=True),
    sa.Column("vaccines_in_gestation", JSONB(), nullable=True),
    sa.Column("orientation_topics", JSONB(), nullable=True),
    sa.Column("weight_gain_weekly_ok", sa.Boolean(), nullable=True),
    sa.Column("birth_plan_elaborated", sa.Boolean(), nullable=True),
)


def upgrade() -> None:
    for column in _PREGNANCY_COLUMNS:
        op.add_column("pregnancies", column)
    for column in _VISIT_COLUMNS:
        op.add_column("pregnancy_visits", column)


def downgrade() -> None:
    for column in reversed(_VISIT_COLUMNS):
        op.drop_column("pregnancy_visits", column.name)
    for column in reversed(_PREGNANCY_COLUMNS):
        op.drop_column("pregnancies", column.name)