"""Prenatal-visit (``PregnancyVisit``) API — creation against an episode, the
gestational age computed *on the visit date*, patient isolation and date
ordering (OB-2)."""

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


async def _pregnancy(client: AsyncClient, auth: dict, pid: str, lmp: str = "2026-01-01") -> str:
    created = await client.post(
        f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": lmp}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def test_create_visit_with_ga_on_visit_date(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_visit@test.com")
    auth = await _auth(client, "admin_visit@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    # No visits yet.
    listed = await client.get(f"/api/patients/{pid}/pregnancies/{preg}/visits", headers=auth)
    assert listed.status_code == 200
    assert listed.json() == []

    created = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/visits",
        headers=auth,
        json={
            "visit_date": "2026-03-12",
            "fundal_height_cm": 14.5,
            "fetal_heart_rate_bpm": 150,
            "presentation": "cephalic",
            "edema": "mild",
            "proteinuria": "negative",
            "notes": "rotina",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    vid = body["id"]
    assert body["pregnancy_id"] == preg
    assert body["visit_date"] == "2026-03-12"
    assert body["fundal_height_cm"] == 14.5
    assert body["fetal_heart_rate_bpm"] == 150
    assert body["presentation"] == "cephalic"
    assert body["edema"] == "mild"
    assert body["proteinuria"] == "negative"
    assert body["notes"] == "rotina"
    # GA computed on the VISIT date (LMP 2026-01-01 -> 2026-03-12 = 10w0d), not today.
    assert body["gestational_age"] == {
        "weeks": 10,
        "days": 0,
        "total_days": 70,
        "as_of": "2026-03-12",
        "basis": "lmp",
    }

    single = await client.get(f"/api/pregnancy-visits/{vid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["gestational_age"]["as_of"] == "2026-03-12"

    # The episode exposes the visit count.
    listed_pregs = await client.get(f"/api/patients/{pid}/pregnancies", headers=auth)
    assert listed_pregs.json()[0]["visit_count"] == 1


async def test_visit_rejects_cross_patient(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_visit_iso@test.com")
    auth = await _auth(client, "admin_visit_iso@test.com")
    pid_a = await _patient(client, auth, "Ana")
    pid_b = await _patient(client, auth, "Bia")
    preg_a = await _pregnancy(client, auth, pid_a)

    # A is the episode's patient; recording under B must be refused (422).
    r = await client.post(
        f"/api/patients/{pid_b}/pregnancies/{preg_a}/visits",
        headers=auth,
        json={"visit_date": "2026-03-12"},
    )
    assert r.status_code == 422, r.text

    # And nothing leaked into B's episode listing (B has no episodes anyway).
    assert (await client.get(f"/api/patients/{pid_b}/pregnancies", headers=auth)).json() == []


async def test_visits_are_ordered_by_date(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_visit_order@test.com")
    auth = await _auth(client, "admin_visit_order@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    # Created out of chronological order on purpose.
    for d in ("2026-06-01", "2026-03-12", "2026-04-20"):
        r = await client.post(
            f"/api/patients/{pid}/pregnancies/{preg}/visits",
            headers=auth,
            json={"visit_date": d},
        )
        assert r.status_code == 201, r.text

    listed = await client.get(f"/api/patients/{pid}/pregnancies/{preg}/visits", headers=auth)
    assert listed.status_code == 200
    dates = [v["visit_date"] for v in listed.json()]
    assert dates == ["2026-03-12", "2026-04-20", "2026-06-01"]
    # GA follows the visit date (ascending with it here).
    weeks = [v["gestational_age"]["weeks"] for v in listed.json()]
    assert weeks == sorted(weeks)


async def test_update_and_delete_visit(client: AsyncClient, db: AsyncSession) -> None:
    await _admin(db, "admin_visit_upd@test.com")
    auth = await _auth(client, "admin_visit_upd@test.com")
    pid = await _patient(client, auth)
    preg = await _pregnancy(client, auth, pid)

    created = await client.post(
        f"/api/patients/{pid}/pregnancies/{preg}/visits",
        headers=auth,
        json={"visit_date": "2026-03-12", "fetal_heart_rate_bpm": 140},
    )
    vid = created.json()["id"]

    patched = await client.patch(
        f"/api/pregnancy-visits/{vid}",
        headers=auth,
        json={"fetal_heart_rate_bpm": 138, "presentation": "breech"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["fetal_heart_rate_bpm"] == 138
    assert patched.json()["presentation"] == "breech"

    deleted = await client.delete(f"/api/pregnancy-visits/{vid}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/pregnancy-visits/{vid}", headers=auth)).status_code == 404
    # Soft-deleted: the episode no longer counts it.
    assert (
        await client.get(f"/api/patients/{pid}/pregnancies/{preg}/visits", headers=auth)
    ).json() == []
    listed_pregs = await client.get(f"/api/patients/{pid}/pregnancies", headers=auth)
    assert listed_pregs.json()[0]["visit_count"] == 0
