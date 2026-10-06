"""add Fase2 prescription state columns

Adds nullable columns for failure tracking, signature state, sync status,
and token emission timestamp — all with safe defaults that do not change
existing rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "h9i0j1k2l3m4"
down_revision = "8f7e7b475af4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Prescription ---
    op.add_column(
        "prescriptions",
        sa.Column("failure_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "prescriptions",
        sa.Column(
            "signature_state",
            sa.String(20),
            nullable=True,
            server_default="none",
        ),
    )

    # --- Prescriber ---
    op.add_column(
        "prescribers",
        sa.Column("sync_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "prescribers",
        sa.Column("sync_error", sa.Text, nullable=True),
    )
    op.add_column(
        "prescribers",
        sa.Column(
            "token_issued_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("prescribers", "token_issued_at")
    op.drop_column("prescribers", "sync_error")
    op.drop_column("prescribers", "sync_status")
    op.drop_column("prescriptions", "signature_state")
    op.drop_column("prescriptions", "failure_reason")