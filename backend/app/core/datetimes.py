"""Typed date/time helpers (WS-5 — prontuário hardening).

The clinical record historically stored every date as an ISO-8601 ``String``
column. WS-5 migrates those to typed ``DateTime(timezone=True)``/``Date``
columns. This module is the single place that knows how to read the *legacy*
strings, so both the Alembic backfill and any remaining string writer share one
rule set:

* date-only string (``YYYY-MM-DD``) → midnight in ``America/Sao_Paulo``;
* naive datetime → interpreted as ``America/Sao_Paulo``;
* aware datetime → kept as the same instant (converted to UTC for storage).

Brazil abolished daylight saving in 2019, so ``America/Sao_Paulo`` has been a
fixed UTC-03 for every row this app holds; we still resolve it through
``zoneinfo`` when the tz database is present and fall back to the fixed offset
otherwise, so parsing never depends on the host having tzdata installed.
"""

from datetime import date, datetime, timedelta, timezone

try:  # pragma: no cover - both branches are trivial
    from zoneinfo import ZoneInfo

    SAO_PAULO = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover - only when the tz database is absent
    SAO_PAULO = timezone(timedelta(hours=-3))

UTC = timezone.utc


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SAO_PAULO)
    return dt.astimezone(UTC)


def parse_datetime(value: object) -> datetime | None:
    """Parse a legacy ISO-8601 value into an aware UTC datetime.

    Returns ``None`` for empty/unparseable input — the backfill must never crash
    on one malformed row (RSK-1), and a null date is a legitimate "unknown".
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    if isinstance(value, date):
        return _to_utc(datetime(value.year, value.month, value.day))

    raw = str(value).strip()
    if not raw:
        return None
    if raw[-1] in ("Z", "z"):  # fromisoformat only accepts 'Z' from Python 3.11 on
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return _to_utc(dt)


def parse_date(value: object) -> date | None:
    """Parse a legacy ISO-8601 value into a pure ``date`` (birth dates).

    Accepts a full datetime and keeps its calendar date. Empty/unparseable → None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def ensure_aware(dt: datetime | None) -> datetime | None:
    """Attach ``America/Sao_Paulo`` to a naive datetime.

    A ``datetime-local`` HTML field sends a naive local time; the caregiver's
    clock is Brazil time, so that is the zone we read it in. Aware values pass
    through unchanged.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=SAO_PAULO)
    return dt
