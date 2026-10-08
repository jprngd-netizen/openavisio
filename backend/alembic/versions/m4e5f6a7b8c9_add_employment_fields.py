"""add employment (vínculo empregatício) fields to patients

The occupational record's cover page ("Capa do Prontuário", Petrobras/SESMT
standard) shows the worker's employment context. These fields did not exist:
they are a 1:1 block on the patient for now (the minimal shape that renders the
cover). A future multi-employer/transfer history, if needed, becomes its own
`Employment` table — do not model N links here.

Every column is nullable with no server default, so existing rows are untouched
and the downgrade is a plain column drop. `admission_date` is an ISO date string
like `birth_date`, so it goes through the same timezone-proof `formatDate`.
"""

import sqlalchemy as sa
from alembic import op

revision = "m4e5f6a7b8c9"
down_revision = "k3c4d5e6f7a8"
branch_labels = None
depends_on = None

EMPLOYMENT: list[tuple[str, sa.types.TypeEngine]] = [
    ("registration", sa.String(64)),
    ("company", sa.String(160)),
    ("contract", sa.String(64)),
    ("job_title", sa.String(120)),
    ("admission_date", sa.String(20)),  # ISO date string, same shape as birth_date
    ("cost_center", sa.String(64)),
    ("work_location", sa.String(160)),
    ("shift", sa.String(64)),  # free text (no fixed enum)
]


def upgrade() -> None:
    for name, type_ in EMPLOYMENT:
        op.add_column("patients", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(EMPLOYMENT):
        op.drop_column("patients", name)
