"""WS-2: GET /patients/{id}/medications/active — active list + duplicate flags."""

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


async def _add(client: AsyncClient, pid: str, auth: dict, **body) -> dict:
    r = await client.post(f"/api/patients/{pid}/medications", headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_active_endpoint_lists_only_currently_effective(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "ws2_active@test.com")
    auth = await _auth(client, "ws2_active@test.com")
    pid = await _patient(client, auth)
    past = (date.today() - timedelta(days=10)).isoformat()
    future = (date.today() + timedelta(days=10)).isoformat()

    ongoing = await _add(client, pid, auth, medication_display="Valproat", effective_start=past)
    future_end = await _add(client, pid, auth, medication_display="Melatonin", effective_start=past, effective_end=future)
    await _add(client, pid, auth, medication_display="Ibuprofen", effective_start=past, effective_end=past)  # ended
    await _add(client, pid, auth, medication_display="Ramipril", effective_start=future)  # not started
    await _add(client, pid, auth, medication_display="Folsäure", status="stopped", effective_start=past)

    r = await client.get(f"/api/patients/{pid}/medications/active", headers=auth)
    assert r.status_code == 200, r.text
    listed = {m["id"]: m for m in r.json()}
    assert set(listed) == {ongoing["id"], future_end["id"]}
    assert all(m["is_active"] is True for m in listed.values())
    assert all(m["duplicate_of"] == [] for m in listed.values())


async def test_active_endpoint_flags_duplicate_substance(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "ws2_dup@test.com")
    auth = await _auth(client, "ws2_dup@test.com")
    pid = await _patient(client, auth)
    past = (date.today() - timedelta(days=10)).isoformat()

    a = await _add(client, pid, auth, medication_display="Dipirona", effective_start=past)
    b = await _add(client, pid, auth, medication_display="Dipirona sódica", effective_start=past)
    lone = await _add(client, pid, auth, medication_display="Paracetamol", effective_start=past)
    # a stopped duplicate must NOT be counted as a live duplicate
    stopped = await _add(client, pid, auth, medication_display="Dipirona", status="stopped", effective_start=past)

    r = await client.get(f"/api/patients/{pid}/medications/active", headers=auth)
    assert r.status_code == 200, r.text
    listed = {m["id"]: m for m in r.json()}

    assert set(listed[a["id"]]["duplicate_of"]) == {b["id"]}
    assert set(listed[b["id"]]["duplicate_of"]) == {a["id"]}
    assert listed[lone["id"]]["duplicate_of"] == []
    assert stopped["id"] not in listed  # stopped med is not active


async def test_active_endpoint_crud_unchanged_and_requires_auth(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "ws2_auth@test.com")
    auth = await _auth(client, "ws2_auth@test.com")
    pid = await _patient(client, auth)
    await _add(client, pid, auth, medication_display="Valproat")

    # the plain list still returns everything, is_active derived as before
    plain = await client.get(f"/api/patients/{pid}/medications", headers=auth)
    assert plain.status_code == 200
    assert all("duplicate_of" not in m for m in plain.json())

    assert (await client.get(f"/api/patients/{pid}/medications/active")).status_code == 401
