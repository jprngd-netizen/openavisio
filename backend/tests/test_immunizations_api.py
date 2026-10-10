"""Structured immunizations API (WS-7): CRUD + controlled status validation."""

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


async def test_immunization_crud_round_trip(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_imm@test.com")
    auth = await _auth(client, "admin_imm@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/immunizations", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{pid}/immunizations",
        headers=auth,
        json={
            "vaccine_code": "207",
            "vaccine_display": "COVID-19",
            "dose_number": 2,
            "occurrence_date": "2021-07-15",
            "lot_number": "AB1234",
            "route": "IM",
            "status": "completed",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["vaccine_display"] == "COVID-19"
    assert body["dose_number"] == 2
    assert body["occurrence_date"] == "2021-07-15"
    assert body["lot_number"] == "AB1234"
    assert body["status"] == "completed"
    iid = body["id"]

    listed = await client.get(f"/api/patients/{pid}/immunizations", headers=auth)
    assert listed.status_code == 200
    assert [i["id"] for i in listed.json()] == [iid]

    single = await client.get(f"/api/immunizations/{iid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["vaccine_display"] == "COVID-19"

    patched = await client.patch(
        f"/api/immunizations/{iid}",
        headers=auth,
        json={"dose_number": 3, "status": "entered_in_error"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["dose_number"] == 3
    assert patched.json()["status"] == "entered_in_error"

    deleted = await client.delete(f"/api/immunizations/{iid}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/immunizations/{iid}", headers=auth)).status_code == 404


async def test_immunization_invalid_status_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_imm_bad@test.com")
    auth = await _auth(client, "admin_imm_bad@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/immunizations",
        headers=auth,
        json={"vaccine_display": "Tétano", "status": "not_a_status"},
    )
    assert r.status_code == 422, r.text


async def test_immunization_missing_display_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_imm_nod@test.com")
    auth = await _auth(client, "admin_imm_nod@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/immunizations",
        headers=auth,
        json={"dose_number": 1},
    )
    assert r.status_code == 422, r.text
