"""Structured family history API (WS-7): CRUD + controlled relationship validation."""

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


async def test_family_history_crud_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fh@test.com")
    auth = await _auth(client, "admin_fh@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/family-history", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{pid}/family-history",
        headers=auth,
        json={
            "relationship": "mother",
            "condition_code": "E11",
            "condition_display": "Diabetes mellitus tipo 2",
            "age_at_onset": 54,
            "deceased": True,
            "note": "DM2; óbito aos 70",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["relationship"] == "mother"
    assert body["condition_display"] == "Diabetes mellitus tipo 2"
    assert body["age_at_onset"] == 54
    assert body["deceased"] is True
    eid = body["id"]

    listed = await client.get(f"/api/patients/{pid}/family-history", headers=auth)
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [eid]

    single = await client.get(f"/api/family-history/{eid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["relationship"] == "mother"

    patched = await client.patch(
        f"/api/family-history/{eid}",
        headers=auth,
        json={"relationship": "grandparent", "age_at_onset": 60},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["relationship"] == "grandparent"
    assert patched.json()["age_at_onset"] == 60

    deleted = await client.delete(f"/api/family-history/{eid}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/family-history/{eid}", headers=auth)).status_code == 404


async def test_family_history_invalid_relationship_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fh_bad@test.com")
    auth = await _auth(client, "admin_fh_bad@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/family-history",
        headers=auth,
        json={"relationship": "cousin", "condition_display": "Hipertensão"},
    )
    assert r.status_code == 422, r.text


async def test_family_history_missing_display_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_fh_nod@test.com")
    auth = await _auth(client, "admin_fh_nod@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/family-history",
        headers=auth,
        json={"relationship": "father"},
    )
    assert r.status_code == 422, r.text
