"""Structured allergies API (WS-1): CRUD + prescription-conflict alerts."""

from __future__ import annotations

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


async def test_allergy_crud_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_allergy@test.com")
    auth = await _auth(client, "admin_allergy@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/allergies", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{pid}/allergies",
        headers=auth,
        json={
            "substance_display": "Dipirona",
            "reaction": "Urticária",
            "severity": "severe",
            "criticality": "high",
            "clinical_status": "active",
            "onset": "2019-05-01T00:00:00-03:00",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["substance_display"] == "Dipirona"
    assert body["severity"] == "severe"
    assert body["criticality"] == "high"
    assert body["clinical_status"] == "active"
    aid = body["id"]

    listed = await client.get(f"/api/patients/{pid}/allergies", headers=auth)
    assert listed.status_code == 200
    assert [a["id"] for a in listed.json()] == [aid]

    single = await client.get(f"/api/allergies/{aid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["substance_display"] == "Dipirona"

    patched = await client.patch(
        f"/api/allergies/{aid}",
        headers=auth,
        json={"severity": "moderate", "clinical_status": "resolved"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["severity"] == "moderate"
    assert patched.json()["clinical_status"] == "resolved"

    filtered = await client.get(f"/api/patients/{pid}/allergies?status=active", headers=auth)
    assert filtered.json() == []

    deleted = await client.delete(f"/api/allergies/{aid}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/allergies/{aid}", headers=auth)).status_code == 404


async def test_allergy_rejects_free_controlled_values(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_allergy_val@test.com")
    auth = await _auth(client, "admin_allergy_val@test.com")
    pid = await _patient(client, auth)

    bad = await client.post(
        f"/api/patients/{pid}/allergies",
        headers=auth,
        json={"substance_display": "Dipirona", "severity": "super-bad"},
    )
    assert bad.status_code == 422, bad.text


async def test_allergy_alerts_route_matches_active_allergy(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_allergy_alert@test.com")
    auth = await _auth(client, "admin_allergy_alert@test.com")
    pid = await _patient(client, auth)

    await client.post(
        f"/api/patients/{pid}/allergies",
        headers=auth,
        json={"substance_display": "Dipirona", "reaction": "Anafilaxia", "severity": "severe", "criticality": "high"},
    )

    hit = await client.get(
        f"/api/patients/{pid}/allergy-alerts?substance=Dipirona&substance=Paracetamol",
        headers=auth,
    )
    assert hit.status_code == 200, hit.text
    conflicts = hit.json()
    assert len(conflicts) == 1
    assert conflicts[0]["substance_display"] == "Dipirona"
    assert conflicts[0]["matched_substance"] == "Dipirona"

    miss = await client.get(f"/api/patients/{pid}/allergy-alerts?substance=Paracetamol", headers=auth)
    assert miss.status_code == 200
    assert miss.json() == []


async def test_allergies_require_auth(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_allergy_auth@test.com")
    auth = await _auth(client, "admin_allergy_auth@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/allergies")).status_code == 401
