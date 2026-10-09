"""WS-3 API: a consultation carries N diagnoses; each shows up in /conditions.

Covers creating a consultation with two diagnoses, editing it (one leaves, the
problem-list Condition survives), re-adding, and the origin exposed on the
condition.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

OWNER_EMAIL = "ws3-api@t.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    u = User(email=OWNER_EMAIL, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="Api", last_name="User")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Api", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": OWNER_EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


DIAG_A = {"cid10_code": "E11", "cid10_display": "Diabetes mellitus tipo 2"}
DIAG_B = {"cid10_code": "I10", "cid10_display": "Hipertensão essencial"}


async def _conditions(client: AsyncClient, pid, h) -> list[dict]:
    r = await client.get(f"/api/patients/{pid}/conditions", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def test_create_consultation_with_two_diagnoses(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    body = {
        "encounter_type": "consulta",
        "encounter_date": "2026-10-05T09:00:00",
        "assessment": "duas comorbidades",
        "diagnoses": [DIAG_A, DIAG_B],
    }
    r = await client.post(f"/api/patients/{p.id}/encounters", json=body, headers=h)
    assert r.status_code == 201, r.text
    enc = r.json()
    eid = enc["id"]
    assert len(enc["diagnoses"]) == 2
    assert {d["cid10_code"] for d in enc["diagnoses"]} == {"E11", "I10"}
    assert all(d["condition_id"] for d in enc["diagnoses"])

    # both diagnoses are now problem-list Conditions with this consultation as origin
    conds = await _conditions(client, p.id, h)
    assert {c["code"] for c in conds} == {"E11", "I10"}
    for c in conds:
        assert len(c["encounters"]) == 1
        assert c["encounters"][0]["encounter_id"] == eid
        assert c["encounters"][0]["cid10_code"] == c["code"]

    # re-fetch the encounter: the diagnoses persist
    r = await client.get(f"/api/encounters/{eid}", headers=h)
    assert len(r.json()["diagnoses"]) == 2


async def test_edit_reconciles_without_deleting_conditions(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    r = await client.post(f"/api/patients/{p.id}/encounters",
                          json={"diagnoses": [DIAG_A, DIAG_B]}, headers=h)
    assert r.status_code == 201, r.text
    eid = r.json()["id"]

    # drop I10 from the consultation
    r = await client.patch(f"/api/encounters/{eid}", json={"diagnoses": [DIAG_A]}, headers=h)
    assert r.status_code == 200, r.text
    assert [d["cid10_code"] for d in r.json()["diagnoses"]] == ["E11"]

    conds = {c["code"]: c for c in await _conditions(client, p.id, h)}
    assert set(conds) == {"E11", "I10"}          # the problem list keeps both
    assert len(conds["I10"]["encounters"]) == 0  # only the link is gone

    # re-add I10: one link again, no duplicate condition
    r = await client.patch(f"/api/encounters/{eid}", json={"diagnoses": [DIAG_A, DIAG_B]}, headers=h)
    assert r.status_code == 200, r.text
    assert len(r.json()["diagnoses"]) == 2
    conds = await _conditions(client, p.id, h)
    assert len(conds) == 2
    assert sum(len(c["encounters"]) for c in conds) == 2


async def test_deleting_consultation_keeps_conditions(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    h = await _auth(client)

    r = await client.post(f"/api/patients/{p.id}/encounters",
                          json={"diagnoses": [DIAG_A, DIAG_B]}, headers=h)
    eid = r.json()["id"]

    assert (await client.delete(f"/api/encounters/{eid}", headers=h)).status_code == 204

    conds = await _conditions(client, p.id, h)
    assert {c["code"] for c in conds} == {"E11", "I10"}
    assert all(c["encounters"] == [] for c in conds)
