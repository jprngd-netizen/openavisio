"""typed date/time columns for the clinical record (WS-5)

Additive and forward-compatible: creates typed ``DateTime(timezone=True)`` /
``Date`` columns *next to* the legacy ISO-8601 ``String`` columns, then backfills
them from those strings. The legacy columns are deliberately left intact so a
rollback is a plain revert — a later cleanup migration (stage S5) drops them.

Backfill rules (see ``app.core.datetimes``):
* date-only string → midnight in America/Sao_Paulo, stored as UTC;
* naive datetime → interpreted as America/Sao_Paulo;
* aware datetime → kept as the same instant;
* empty/unparseable → NULL (a malformed row never aborts the migration).

Revision ID: w5a1b2c3d4e5
Revises: o7b8c9d0e1f2
Create Date: 2026-10-09

"""
import sqlalchemy as sa
from alembic import op

from app.core.datetimes import parse_date, parse_datetime

revision = "w5a1b2c3d4e5"
down_revision = "o7b8c9d0e1f2"
branch_labels = None
depends_on = None

# (table, legacy string column, new typed column)
_DATETIME_COLUMNS = [
    ("encounters", "encounter_date", "encounter_date_ts"),
    ("conditions", "recorded_date", "recorded_date_ts"),
    ("conditions", "onset_date_time", "onset_date_time_ts"),
    ("conditions", "abatement_date_time", "abatement_date_time_ts"),
    ("observations", "effective_date_time", "effective_date_time_ts"),
    ("medication_statements", "date_asserted", "date_asserted_ts"),
    ("medication_statements", "effective_start", "effective_start_ts"),
    ("medication_statements", "effective_end", "effective_end_ts"),
    ("calendar_events", "start_at", "start_at_ts"),
    ("calendar_events", "end_at", "end_at_ts"),
]
_DATE_COLUMNS = [
    ("patients", "birth_date", "birth_date_ts"),
]


def _backfill(bind, table: str, old: str, new: str, parser) -> None:
    rows = bind.execute(
        sa.text(f"SELECT id, {old} FROM {table} WHERE {old} IS NOT NULL")
    ).fetchall()
    for row_id, legacy in rows:
        value = parser(legacy)
        if value is None:
            continue
        bind.execute(
            sa.text(f"UPDATE {table} SET {new} = :v WHERE id = :i"),
            {"v": value, "i": row_id},
        )


def upgrade() -> None:
    for table, _old, new in _DATETIME_COLUMNS:
        op.add_column(table, sa.Column(new, sa.DateTime(timezone=True), nullable=True))
    for table, _old, new in _DATE_COLUMNS:
        op.add_column(table, sa.Column(new, sa.Date(), nullable=True))

    bind = op.get_bind()
    for table, old, new in _DATETIME_COLUMNS:
        _backfill(bind, table, old, new, parse_datetime)
    for table, old, new in _DATE_COLUMNS:
        _backfill(bind, table, old, new, parse_date)


def downgrade() -> None:
    for table, _old, new in _DATE_COLUMNS:
        op.drop_column(table, new)
    for table, _old, new in _DATETIME_COLUMNS:
        op.drop_column(table, new)
