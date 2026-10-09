"""unblock inserts after WS-5: relax the legacy calendar_events.start_at (WS-5b)

WS-5 (``w5a1b2c3d4e5``) introduced the typed ``start_at_ts`` column and remapped
the ``CalendarEvent.start_at`` attribute onto it, so the ORM no longer writes the
legacy ISO-8601 ``start_at`` String column. That column was created **NOT NULL**
by the initial schema (``ea27601363a6``, ``calendar_events.start_at``), which made
every insert against a migration-built schema fail::

    NotNullViolationError: null value in column "start_at" of relation
    "calendar_events" violates not-null constraint

``Base.metadata.create_all`` (used by the test conftest) never produces the legacy
column at all, which is why the bug only surfaced against a migrated schema — a
model/migration parity gap.

This migration is deliberately additive and minimal: it only relaxes the legacy
column to nullable. The column itself is still kept (it is retired, not dropped —
dropping it stays a job for the later stage-S5 cleanup) so a WS-5 rollback remains
a plain revert. A scan of the migrated schema confirmed ``start_at`` was the only
unmapped, NOT-NULL, default-less legacy column left by WS-5; the other legacy date
columns (``end_at``, ``encounter_date``, ``effective_date_time``, …) were already
nullable.

Revision ID: z7v8w9x0y1z2
Revises: y7c3d4e5f6a7
Create Date: 2026-10-09

"""

import sqlalchemy as sa
from alembic import op

revision = "z7v8w9x0y1z2"
down_revision = "y7c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy, unread column — let the ORM insert without populating it.
    op.alter_column(
        "calendar_events",
        "start_at",
        existing_type=sa.String(length=50),
        nullable=True,
    )


def downgrade() -> None:
    # Restore the pre-WS-5b shape. The column is not written by current code, so
    # repopulate it from the typed source before re-imposing NOT NULL; otherwise
    # the constraint cannot be re-added on a schema that has rows.
    op.execute(
        """
        UPDATE calendar_events
        SET start_at = to_char(start_at_ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS')
        WHERE start_at IS NULL AND start_at_ts IS NOT NULL
        """
    )
    op.alter_column(
        "calendar_events",
        "start_at",
        existing_type=sa.String(length=50),
        nullable=False,
    )
