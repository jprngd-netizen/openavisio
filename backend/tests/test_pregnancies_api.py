"""Obstetric episode (``Pregnancy``) API — CRUD, derived IG/DPP, derived GOP and
patient isolation (OB-1)."""

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


async def _patient(client: AsyncClient, auth: dict, name: str = "Ana") -> str:
    created = await client.post(
        "/api/patients", headers=auth, json={"given_name": name, "family_name": "Alves"}
    )
    assert created.status_code in (200, 201), created.text
    return created.json()["id"]


async def test_pregnancy_crud_and_naegele(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_preg@test.com")
    auth = await _auth(client, "admin_preg@test.com")
    pid = await _patient(client, auth)

    assert (await client.get(f"/api/patients/{pid}/pregnancies", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{pid}/pregnancies",
        headers=auth,
        json={"lmp_date": "2026-01-01", "status": "active"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    # DPP derived by Naegele (LMP + 280 days) when not supplied.
    assert body["estimated_due_date"] == "2026-10-08"
    assert body["lmp_date"] == "2026-01-01"
    assert body["status"] == "active"
    assert body["ended_at"] is None
    pid_preg = body["id"]

    listed = await client.get(f"/api/patients/{pid}/pregnancies", headers=auth)
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [pid_preg]

    single = await client.get(f"/api/pregnancies/{pid_preg}", headers=auth)
    assert single.status_code == 200
    assert single.json()["estimated_due_date"] == "2026-10-08"

    patched = await client.patch(
        f"/api/pregnancies/{pid_preg}",
        headers=auth,
        json={"status": "completed", "ended_at": "2026-10-08", "notes": "parto vaginal"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "completed"
    assert patched.json()["ended_at"] == "2026-10-08"
    assert patched.json()["notes"] == "parto vaginal"

    deleted = await client.delete(f"/api/pregnancies/{pid_preg}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/pregnancies/{pid_preg}", headers=auth)).status_code == 404


async def test_pregnancy_invalid_status_rejected(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_preg_bad@test.com")
    auth = await _auth(client, "admin_preg_bad@test.com")
    pid = await _patient(client, auth)

    r = await client.post(
        f"/api/patients/{pid}/pregnancies",
        headers=auth,
        json={"lmp_date": "2026-01-01", "status": "not_a_status"},
    )
    assert r.status_code == 422, r.text


async def test_pregnancy_gestational_age_endpoint(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_preg_ga@test.com")
    auth = await _auth(client, "admin_preg_ga@test.com")
    pid = await _patient(client, auth)

    created = await client.post(
        f"/api/patients/{pid}/pregnancies",
        headers=auth,
        json={
            "lmp_date": "2026-01-01",
            "ultrasound_due_date": "2026-10-20",
            "ultrasound_date": "2026-03-01",
        },
    )
    preg = created.json()["id"]

    # Explicit as_of — the ultrasound-corrected DPP prevails (19w6d).
    ga = await client.get(f"/api/pregnancies/{preg}/gestational-age?as_of=2026-06-01", headers=auth)
    assert ga.status_code == 200, ga.text
    assert ga.json() == {
        "weeks": 19,
        "days": 6,
        "total_days": 139,
        "as_of": "2026-06-01",
        "basis": "ultrasound",
    }

    # The endpoint refuses an episode with no dating basis.
    no_basis = await client.post(
        f"/api/patients/{pid}/pregnancies", headers=auth, json={"status": "active"}
    )
    nb = no_basis.json()["id"]
    assert (
        await client.get(f"/api/pregnancies/{nb}/gestational-age?as_of=2026-06-01", headers=auth)
    ).status_code == 422

    # as_of is required.
    assert (await client.get(f"/api/pregnancies/{preg}/gestational-age", headers=auth)).status_code == 422


async def test_derived_gop(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_gop@test.com")
    auth = await _auth(client, "admin_gop@test.com")
    pid = await _patient(client, auth)

    episodes = [
        ("2026-01-01", "active"),
        ("2025-01-01", "completed"),
        ("2024-01-01", "miscarriage"),
        ("2023-01-01", "terminated"),
        ("2022-01-01", "ectopic"),
        ("2021-01-01", "fetal_death"),
    ]
    for lmp, status_value in episodes:
        r = await client.post(
            f"/api/patients/{pid}/pregnancies",
            headers=auth,
            json={"lmp_date": lmp, "status": status_value},
        )
        assert r.status_code == 201, r.text

    summary = await client.get(f"/api/patients/{pid}/obstetric-summary", headers=auth)
    assert summary.status_code == 200, summary.text
    # G = all episodes; P = delivered; A = miscarriage + terminated + ectopic.
    # fetal_death is neither a delivery nor a (pre-viability) loss here — OB-3
    # refines it; it still counts toward gravida.
    assert summary.json() == {"gravida": 6, "para": 1, "aborto": 3}


async def test_pregnancy_listing_is_isolated_by_patient(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_iso@test.com")
    auth = await _auth(client, "admin_iso@test.com")
    pid_a = await _patient(client, auth, "Ana")
    pid_b = await _patient(client, auth, "Bia")

    a = await client.post(
        f"/api/patients/{pid_a}/pregnancies", headers=auth, json={"lmp_date": "2026-01-01"}
    )
    b = await client.post(
        f"/api/patients/{pid_b}/pregnancies", headers=auth, json={"lmp_date": "2026-02-01"}
    )
    assert a.status_code == 201 and b.status_code == 201

    list_a = (await client.get(f"/api/patients/{pid_a}/pregnancies", headers=auth)).json()
    list_b = (await client.get(f"/api/patients/{pid_b}/pregnancies", headers=auth)).json()
    assert [p["id"] for p in list_a] == [a.json()["id"]]
    assert [p["id"] for p in list_b] == [b.json()["id"]]

    # The derived GOP is per-patient too.
    gop_a = (await client.get(f"/api/patients/{pid_a}/obstetric-summary", headers=auth)).json()
    gop_b = (await client.get(f"/api/patients/{pid_b}/obstetric-summary", headers=auth)).json()
    assert gop_a["gravida"] == 1 and gop_b["gravida"] == 1
