"""reconcile model↔migration NOT NULL drift (WS-12)

Several migrations created columns *nullable* while the SQLAlchemy models
declare them NOT NULL (``Mapped[datetime]`` infers ``NOT NULL``; some use
``nullable=False`` explicitly). Under ``Base.metadata.create_all`` (the test
suite) these columns are NOT NULL, but under the real migration chain — the one
production runs — they were relaxed:

* ``calendar_events.start_at_ts`` — WS-5 (``w5a1b2c3d4e5``) added the typed
  column nullable on purpose so a malformed legacy value would not abort the
  backfill, but the ORM maps it as required;
* ``created_at`` / ``updated_at`` / ``is_deleted`` on ``clinical_histories``,
  ``document_favorites``, ``patient_favorites`` and ``patient_keys`` — the
  migrations that introduced these tables forgot ``nullable=False``;
* ``organization.default_language`` (``h8c9d0e1f2g3``).

This is *permissive* drift: a migrated database accepts inserts the model would
not build, so it never failed the suite. It is reconciled here anyway because
production reads the migrated schema, which must enforce what the models
promise.

Safety: every column already carries a server default (``now()`` / ``false`` /
``'en'``) and is populated for existing rows. ``start_at_ts`` is defensively
backfilled from the row's ``created_at`` for the pathological case of a legacy
``start_at`` that WS-5 could not parse (leaving it NULL), so ``SET NOT NULL``
cannot fail on real data.

Cosmetic drift is deliberately NOT touched here — the legacy ISO-8601 string
columns WS-5 kept for a stage-S5 cleanup, and the unique-constraint-vs-unique-
index *naming* differences (``uq_*`` / ``ix_*``). Neither has a functional
effect; both are documented as accepted in ``docs``/WS-12.

Revision ID: a9b8c7d6e5f4
Revises: e7f8a9b0c1d2
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op

revision = "a9b8c7d6e5f4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None

_TS = sa.DateTime(timezone=True)

# (table, column) — timestamp columns the models declare NOT NULL.
_TS_NOT_NULL = [
    ("clinical_histories", "created_at"),
    ("clinical_histories", "updated_at"),
    ("document_favorites", "created_at"),
    ("document_favorites", "updated_at"),
    ("patient_favorites", "created_at"),
    ("patient_favorites", "updated_at"),
    ("patient_keys", "created_at"),
    ("patient_keys", "updated_at"),
]

# (table, column, server_default) — boolean columns the models declare NOT NULL.
_BOOL_NOT_NULL = [
    ("document_favorites", "is_deleted", "false"),
    ("patient_favorites", "is_deleted", "false"),
    ("patient_keys", "is_deleted", "false"),
]


def upgrade() -> None:
    # calendar_events.start_at_ts: guarantee no NULL before tightening. Any row
    # left NULL by WS-5 had an unparseable legacy start_at; fall back to the
    # row's creation time (always present) so the ALTER cannot fail.
    op.execute(
        "UPDATE calendar_events SET start_at_ts = created_at "
        "WHERE start_at_ts IS NULL"
    )
    op.alter_column(
        "calendar_events",
        "start_at_ts",
        existing_type=_TS,
        nullable=False,
    )

    for table, column in _TS_NOT_NULL:
        op.alter_column(table, column, existing_type=_TS, nullable=False)

    for table, column, default in _BOOL_NOT_NULL:
        op.alter_column(
            table,
            column,
            existing_type=sa.Boolean(),
            server_default=sa.text(default),
            nullable=False,
        )

    op.alter_column(
        "organization",
        "default_language",
        existing_type=sa.String(10),
        server_default=sa.text("'en'"),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "organization",
        "default_language",
        existing_type=sa.String(10),
        server_default=sa.text("'en'"),
        nullable=True,
    )

    for table, column, _default in _BOOL_NOT_NULL:
        op.alter_column(table, column, existing_type=sa.Boolean(), nullable=True)

    for table, column in _TS_NOT_NULL:
        op.alter_column(table, column, existing_type=_TS, nullable=True)

    op.alter_column(
        "calendar_events",
        "start_at_ts",
        existing_type=_TS,
        nullable=True,
    )
