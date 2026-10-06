"""add contact and address fields to patients and prescribers

Adds CNS plus a Brazilian address block to both patients and prescribers.
Every column is nullable with no server default, so existing rows are untouched
and the downgrade is a plain column drop.

CPF is NOT added here: `cpf_encrypted`/`cpf_last4` already exist on both tables
(patients got them with the prescription migration); this revision only wires
them up in the API layer.
"""

import sqlalchemy as sa
from alembic import op

revision = "i1a2b3c4d5e6"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None

# (name, type) — built per table so the Column objects are never shared.
ADDRESS: list[tuple[str, sa.types.TypeEngine]] = [
    ("cep", sa.String(9)),
    ("street", sa.String(256)),
    ("street_number", sa.String(20)),
    ("complement", sa.String(120)),
    ("district", sa.String(120)),
    ("city_name", sa.String(120)),
    ("state_code", sa.String(2)),
]


def upgrade() -> None:
    op.add_column("patients", sa.Column("cns", sa.String(20), nullable=True))
    for name, type_ in ADDRESS:
        op.add_column("patients", sa.Column(name, type_, nullable=True))
        op.add_column("prescribers", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _ in reversed(ADDRESS):
        op.drop_column("prescribers", name)
        op.drop_column("patients", name)
    op.drop_column("patients", "cns")