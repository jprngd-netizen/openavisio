"""drop occupational fields (clinical-only prontuário)

Reverts the occupational-health additions now that the record is clinical-only:
- `patients`: the employment block (registration, company, contract, job_title,
  admission_date, cost_center, work_location, shift) added by m4e5f6a7b8c9.
- `clinical_histories`: previous_employments and exposures (JSONB) added by
  n5f6a7b8c9d0.

The remaining clinical columns (personal/family/surgical history, allergies,
habits) are untouched.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "o7b8c9d0e1f2"
down_revision = "n5f6a7b8c9d0"
branch_labels = None
depends_on = None

_PATIENT_COLUMNS = [
    ("registration", sa.String(64)),
    ("company", sa.String(160)),
    ("contract", sa.String(64)),
    ("job_title", sa.String(120)),
    ("admission_date", sa.String(20)),
    ("cost_center", sa.String(64)),
    ("work_location", sa.String(160)),
    ("shift", sa.String(64)),
]


def upgrade() -> None:
    for name, _type in _PATIENT_COLUMNS:
        op.drop_column("patients", name)
    op.drop_column("clinical_histories", "previous_employments")
    op.drop_column("clinical_histories", "exposures")


def downgrade() -> None:
    op.add_column("clinical_histories", sa.Column("previous_employments", JSONB()))
    op.add_column("clinical_histories", sa.Column("exposures", JSONB()))
    for name, type_ in _PATIENT_COLUMNS:
        op.add_column("patients", sa.Column(name, type_))
