"""WS-10 (continuity of care): encounter_type taxonomy, scheduled follow-up and
referrals (encaminhamento).

Covers:
* the controlled ``encounter_type`` taxonomy (DEC-3), with legacy free values
  still accepted so existing contracts keep working;
* ``POST /api/encounters/{id}/follow-up`` creating a linked CalendarEvent;
* Referral CRUD + StrEnum validation (invalid status → 422).
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

EMAIL = "ws10@test.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    owner = User(email=EMAIL, hashed_password=hash_password(PASSWORD), role="user",
                 is_active=True, first_name="W", last_name="Ten")
    db.add(owner)
    await db.commit()
    await db.refresh(owner)
    p = Patient(given_name="Ana", family_name="Cont", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return owner, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _encounter(client: AsyncClient, pid, auth: dict, **extra) -> dict:
    body = {"encounter_date": "2026-10-07T10:30:00", "plan": "retorno em 15 dias"}
    body.update(extra)
    r = await client.post(f"/api/patients/{pid}/encounters", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


# --- encounter_type taxonomy (DEC-3) ---------------------------------------


async def test_encounter_type_accepts_taxonomy_values(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)

    for value in ("outpatient", "emergency", "telemedicine", "follow_up", "home_visit", "other"):
        enc = await _encounter(client, p.id, auth, encounter_type=value)
        assert enc["encounter_type"] == value


async def test_encounter_type_keeps_legacy_free_values(client: AsyncClient, db: AsyncSession):
    """The column stays a free String: historical labels still sail through."""
    _, p = await _setup(db)
    auth = await _auth(client)

    enc = await _encounter(client, p.id, auth, encounter_type="consulta")
    assert enc["encounter_type"] == "consulta"


async def test_encounter_type_rejects_unknown_value(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)

    r = await client.post(
        f"/api/patients/{p.id}/encounters",
        json={"encounter_date": "2026-10-07T10:30:00", "encounter_type": "not_a_type"},
        headers=auth,
    )
    assert r.status_code == 422, r.text


# --- scheduled follow-up (encounter ↔ CalendarEvent) -----------------------


async def test_follow_up_creates_linked_calendar_event(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth, encounter_type="outpatient")
    eid = enc["id"]
    assert enc["follow_ups"] == []

    r = await client.post(
        f"/api/encounters/{eid}/follow-up",
        json={"start_at": "2026-10-22T09:00:00", "title": "Retorno pós-consulta",
              "purpose": "Avaliar resposta ao tratamento"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["category"] == "appointment"
    assert ev["encounter_id"] == eid
    assert ev["patient_id"] == str(p.id)
    assert ev["title"] == "Retorno pós-consulta"
    assert ev["purpose"] == "Avaliar resposta ao tratamento"

    # the consultation now exposes its return
    got = (await client.get(f"/api/encounters/{eid}", headers=auth)).json()
    assert [f["id"] for f in got["follow_ups"]] == [ev["id"]]

    # and it shows on the calendar, linked back to the consultation
    feed = (await client.get(f"/api/patients/{p.id}/calendar/feed", headers=auth)).json()
    linked = [i for i in feed if i["id"] == ev["id"]]
    assert len(linked) == 1
    assert linked[0]["type"] == "appointment"
    assert linked[0]["encounter_id"] == eid


async def test_follow_up_defaults_title(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)

    r = await client.post(
        f"/api/encounters/{enc['id']}/follow-up",
        json={"start_at": "2026-11-01T08:00:00"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    assert r.json()["title"] == "Retorno"


# --- referrals -------------------------------------------------------------


async def test_referral_crud_roundtrip(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    eid = enc["id"]

    assert (await client.get(f"/api/patients/{p.id}/referrals", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{p.id}/referrals",
        json={
            "target_specialty": "Cardiologia",
            "encounter_id": eid,
            "reason": "Hipertensão não controlada",
            "status": "sent",
            "date": "2026-10-08",
            "note": "Encaminhado ao serviço de referência",
        },
        headers=auth,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["target_specialty"] == "Cardiologia"
    assert body["encounter_id"] == eid
    assert body["status"] == "sent"
    assert body["date"] == "2026-10-08"
    rid = body["id"]

    listed = await client.get(f"/api/patients/{p.id}/referrals", headers=auth)
    assert [x["id"] for x in listed.json()] == [rid]

    single = await client.get(f"/api/referrals/{rid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["target_specialty"] == "Cardiologia"

    # the consultation exposes its referrals
    got = (await client.get(f"/api/encounters/{eid}", headers=auth)).json()
    assert [x["id"] for x in got["referrals"]] == [rid]

    patched = await client.patch(
        f"/api/referrals/{rid}", json={"status": "completed"}, headers=auth
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"

    assert (await client.delete(f"/api/referrals/{rid}", headers=auth)).status_code == 204
    assert (await client.get(f"/api/referrals/{rid}", headers=auth)).status_code == 404


async def test_referral_invalid_status_rejected(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)

    r = await client.post(
        f"/api/patients/{p.id}/referrals",
        json={"target_specialty": "Ortopedia", "status": "not_a_status"},
        headers=auth,
    )
    assert r.status_code == 422, r.text


async def test_referral_missing_specialty_rejected(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)

    r = await client.post(f"/api/patients/{p.id}/referrals", json={"reason": "x"}, headers=auth)
    assert r.status_code == 422, r.text


async def test_referral_requires_patient_access(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    # a second user with no grant
    other = User(email="ws10-stranger@test.com", hashed_password=hash_password(PASSWORD),
                 role="user", is_active=True, first_name="S", last_name="tranger")
    db.add(other)
    await db.commit()
    r = await client.post("/api/auth/login", json={"email": "ws10-stranger@test.com", "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    listed = await client.get(f"/api/patients/{p.id}/referrals", headers=h)
    assert listed.status_code in (403, 404), listed.text

    created = await client.post(
        f"/api/patients/{p.id}/referrals",
        json={"target_specialty": "Cardiologia"},
        headers=h,
    )
    assert created.status_code in (403, 404), created.text
