"""WS-9: GET /patients/{id}/safety-summary — the chart-cover safety banner.

One aggregated read returning only the active allergies, the currently-effective
medications and the active problems.
"""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


async def _admin(db: AsyncSession, email: str) -> None:
    db.add(User(email=email, hashed_password=hash_password("Password1!"), role="admin", is_active=True))
    await db.commit()


async def _auth(client: AsyncClient, email: str) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _patient(client: AsyncClient, auth: dict) -> str:
    created = await client.post("/api/patients", headers=auth, json={"given_name": "Ana", "family_name": "Alves"})
    assert created.status_code in (200, 201), created.text
    return created.json()["id"]


async def test_safety_summary_empty_patient(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "ws9_empty@test.com")
    auth = await _auth(client, "ws9_empty@test.com")
    pid = await _patient(client, auth)

    r = await client.get(f"/api/patients/{pid}/safety-summary", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"allergies": [], "medications": [], "conditions": []}


async def test_safety_summary_returns_only_active_on_every_axis(
    client: AsyncClient, db: AsyncSession
) -> None:
    await _admin(db, "ws9_active@test.com")
    auth = await _auth(client, "ws9_active@test.com")
    pid = await _patient(client, auth)
    past = (date.today() - timedelta(days=10)).isoformat()
    future = (date.today() + timedelta(days=10)).isoformat()

    # Allergies: one active, one resolved — only the active one is returned.
    active_allergy = await client.post(
        f"/api/patients/{pid}/allergies",
        headers=auth,
        json={"substance_display": "Dipirona", "severity": "severe", "criticality": "high", "clinical_status": "active"},
    )
    assert active_allergy.status_code == 201, active_allergy.text
    resolved = await client.post(
        f"/api/patients/{pid}/allergies",
        headers=auth,
        json={"substance_display": "Penicilina", "clinical_status": "resolved"},
    )
    assert resolved.status_code == 201, resolved.text

    # Medications: one in force, one stopped, one not started yet.
    ongoing = await client.post(
        f"/api/patients/{pid}/medications",
        headers=auth,
        json={"medication_display": "Valproat", "effective_start": past},
    )
    assert ongoing.status_code == 201, ongoing.text
    await client.post(
        f"/api/patients/{pid}/medications",
        headers=auth,
        json={"medication_display": "Folsäure", "status": "stopped", "effective_start": past},
    )
    await client.post(
        f"/api/patients/{pid}/medications",
        headers=auth,
        json={"medication_display": "Ramipril", "effective_start": future},
    )

    # Conditions: one active, one resolved.
    active_cond = await client.post(
        f"/api/patients/{pid}/conditions",
        headers=auth,
        json={"code_display": "Hipertensão", "clinical_status": "active"},
    )
    assert active_cond.status_code == 201, active_cond.text
    await client.post(
        f"/api/patients/{pid}/conditions",
        headers=auth,
        json={"code_display": "Bronquite", "clinical_status": "resolved"},
    )

    r = await client.get(f"/api/patients/{pid}/safety-summary", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()

    assert [a["substance_display"] for a in body["allergies"]] == ["Dipirona"]
    assert [m["medication_display"] for m in body["medications"]] == ["Valproat"]
    assert [c["code_display"] for c in body["conditions"]] == ["Hipertensão"]

    # The payload stays lean: no CRUD-only fields leak in.
    assert "duplicate_of" not in body["medications"][0]
    assert "patient_id" not in body["allergies"][0]
    assert "sources" not in body["conditions"][0]


async def test_safety_summary_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "ws9_auth@test.com")
    auth = await _auth(client, "ws9_auth@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/safety-summary")).status_code == 401
