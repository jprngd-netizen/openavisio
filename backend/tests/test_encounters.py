"""Prontuário: Encounter (consulta/evolução SOAP) CRUD + access control.

Covers the new `encounters` resource: create with SOAP fields + CID-10, list,
get, partial patch (untouched fields preserved), soft delete, and that a user
without a grant on the patient is refused.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

OWNER_EMAIL = "enc-owner@t.com"
STRANGER_EMAIL = "enc-stranger@t.com"
PASSWORD = "Pass1!"


async def _user(db: AsyncSession, email: str) -> User:
    u = User(email=email, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="E", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _setup(db: AsyncSession):
    owner = await _user(db, OWNER_EMAIL)
    stranger = await _user(db, STRANGER_EMAIL)
    p = Patient(given_name="Ana", family_name="Test", created_by=owner.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=owner.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return owner, stranger, p


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_encounter_crud_roundtrip(client: AsyncClient, db: AsyncSession):
    _, _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    body = {
        "encounter_type": "consulta",
        "encounter_date": "2026-10-07T10:30:00",
        "chief_complaint": "dor de cabeça",
        "history": "cefaleia há 3 dias",
        "physical_exam": "PA 130/80, afebril",
        "assessment": "cefaleia tensional",
        "plan": "analgésico e retorno em 7 dias",
        "cid10_code": "G44.2",
        "cid10_display": "Cefaleia do tipo tensional",
    }

    # create
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text
    enc = r.json()
    assert enc["status"] == "finished"
    assert enc["physical_exam"] == "PA 130/80, afebril"
    assert enc["cid10_code"] == "G44.2"
    assert enc["patient_id"] == str(p.id)
    eid = enc["id"]

    # list
    r = await client.get(f"/api/patients/{p.id}/encounters", headers=h)
    assert r.status_code == 200, r.text
    assert [e["id"] for e in r.json()] == [eid]

    # get
    r = await client.get(f"/api/encounters/{eid}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["assessment"] == "cefaleia tensional"

    # partial patch — only the provided field changes
    r = await client.patch(f"/api/encounters/{eid}", json={"plan": "retorno em 15 dias"}, headers=h)
    assert r.status_code == 200, r.text
    patched = r.json()
    assert patched["plan"] == "retorno em 15 dias"
    assert patched["assessment"] == "cefaleia tensional"
    assert patched["physical_exam"] == "PA 130/80, afebril"

    # soft delete
    r = await client.delete(f"/api/encounters/{eid}", headers=h)
    assert r.status_code == 204, r.text
    assert (await client.get(f"/api/encounters/{eid}", headers=h)).status_code == 404
    r = await client.get(f"/api/patients/{p.id}/encounters", headers=h)
    assert r.json() == []


async def test_encounter_requires_patient_access(client: AsyncClient, db: AsyncSession):
    _, _, p = await _setup(db)
    h = await _auth(client, STRANGER_EMAIL)

    r = await client.get(f"/api/patients/{p.id}/encounters", headers=h)
    assert r.status_code in (403, 404), r.text

    r = await client.post(f"/api/patients/{p.id}/encounters", json={"plan": "x"}, headers=h)
    assert r.status_code in (403, 404), r.text


async def test_encounter_vitals_are_linked_observations(client: AsyncClient, db: AsyncSession):
    """Vitals recorded in a consultation are Observation rows linked to it, so the
    measurements history and the encounter record share one source of truth."""
    _, _, p = await _setup(db)
    h = await _auth(client, OWNER_EMAIL)

    body = {
        "encounter_type": "consulta",
        "encounter_date": "2026-10-07",
        "measurements": [
            {"code": "body-weight", "code_display": "Weight", "value_quantity": 107.4, "value_unit": "kg"},
            {"code": "blood-pressure-systolic", "code_display": "BP systolic", "value_quantity": 130, "value_unit": "mmHg"},
            {"code": "blood-pressure-diastolic", "code_display": "BP diastolic", "value_quantity": 80, "value_unit": "mmHg"},
        ],
    }
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text
    enc = r.json()
    eid = enc["id"]
    assert {m["code"] for m in enc["measurements"]} == {
        "body-weight", "blood-pressure-systolic", "blood-pressure-diastolic"
    }

    # the same rows appear in the patient's measurement feed, tagged to the encounter
    r = await client.get(f"/api/patients/{p.id}/observations?category=measurement", headers=h)
    assert r.status_code == 200, r.text
    obs = r.json()
    assert len(obs) == 3
    assert all(o["encounter_id"] == eid for o in obs)
    assert all(o["effective_date_time"].startswith("2026-10-07") for o in obs)

    # patching replaces the vitals set (old rows are soft-deleted)
    r = await client.patch(
        f"/api/encounters/{eid}",
        json={"measurements": [
            {"code": "body-temperature", "code_display": "Temperature", "value_quantity": 36.8, "value_unit": "°C"}
        ]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert [m["code"] for m in r.json()["measurements"]] == ["body-temperature"]
    r = await client.get(f"/api/patients/{p.id}/observations?category=measurement", headers=h)
    assert [o["code"] for o in r.json()] == ["body-temperature"]

    # deleting the encounter soft-deletes its vitals too
    assert (await client.delete(f"/api/encounters/{eid}", headers=h)).status_code == 204
    r = await client.get(f"/api/patients/{p.id}/observations?category=measurement", headers=h)
    assert r.json() == []