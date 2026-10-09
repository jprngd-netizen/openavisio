"""WS-5: typed date/time foundation.

Unit tests for the legacy-string parser that both the Alembic backfill and the
schemas rely on, plus an end-to-end check that the API stores/returns typed
dates (a date-only field and a naive ``datetime-local`` value) as aware ISO-8601.
"""

from datetime import UTC, date, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetimes import SAO_PAULO, ensure_aware, parse_date, parse_datetime
from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

# --- parser ------------------------------------------------------------------


def test_parse_datetime_date_only_is_midnight_sao_paulo():
    # date-only → 00:00 in America/Sao_Paulo, stored as the UTC instant (03:00Z)
    assert parse_datetime("2026-10-07") == datetime(2026, 10, 7, 3, 0, tzinfo=UTC)


def test_parse_datetime_naive_is_read_in_sao_paulo():
    # a naive datetime is assumed to be Brazil local time (UTC-03)
    assert parse_datetime("2026-10-07T10:30:00") == datetime(2026, 10, 7, 13, 30, tzinfo=UTC)


def test_parse_datetime_with_offset_keeps_the_instant():
    assert parse_datetime("2026-10-07T10:30:00-03:00") == datetime(2026, 10, 7, 13, 30, tzinfo=UTC)


def test_parse_datetime_z_suffix():
    assert parse_datetime("2026-10-07T13:30:00Z") == datetime(2026, 10, 7, 13, 30, tzinfo=UTC)


def test_parse_datetime_accepts_a_datetime_object():
    aware = datetime(2026, 10, 7, 10, 30, tzinfo=SAO_PAULO)
    assert parse_datetime(aware) == datetime(2026, 10, 7, 13, 30, tzinfo=UTC)


def test_parse_datetime_empty_and_invalid_are_none():
    for bad in (None, "", "   ", "not-a-date", "2026-13-40"):
        assert parse_datetime(bad) is None


def test_parse_date_only_date():
    assert parse_date("2015-04-02") == date(2015, 4, 2)


def test_parse_date_from_datetime_keeps_the_calendar_day():
    assert parse_date("2015-04-02T23:00:00") == date(2015, 4, 2)


def test_parse_date_empty_and_invalid_are_none():
    for bad in (None, "", "  ", "yesterday"):
        assert parse_date(bad) is None


def test_ensure_aware_attaches_sao_paulo_to_naive_only():
    naive = datetime(2026, 10, 7, 10, 30)
    assert ensure_aware(naive).utcoffset() == SAO_PAULO.utcoffset(naive)
    aware = datetime(2026, 10, 7, 10, 30, tzinfo=UTC)
    assert ensure_aware(aware) is aware


# --- API round-trip ----------------------------------------------------------


async def _setup(db: AsyncSession):
    u = User(email="typed@t.com", hashed_password=hash_password("Pass1!"), role="user",
             is_active=True, first_name="T", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Test", birth_date=date(1990, 1, 1), created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": "typed@t.com", "password": "Pass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_api_returns_typed_dates_as_iso_strings(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    # a date-only encounter_date is read as Sao Paulo midnight, returned as ISO-8601
    r = await client.post(f"/api/patients/{p.id}/encounters", json={"encounter_date": "2026-10-07"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["encounter_date"].startswith("2026-10-07T00:00:00")

    # a naive datetime-local value (09:00 local) round-trips as the same local time
    r = await client.post(f"/api/patients/{p.id}/calendar/events",
                          json={"title": "Consulta", "start_at": "2026-05-10T09:00:00"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["start_at"].startswith("2026-05-10T09:00:00")


async def test_patient_birth_date_is_a_pure_calendar_date(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)
    r = await client.get(f"/api/patients/{p.id}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["birth_date"] == "1990-01-01"
