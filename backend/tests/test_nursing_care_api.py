"""OB-5: nursing-care records (general + obstetric).

A nursing record is *dated and frozen*: ``occurred_at`` is the instant the care
happened (a typed ``DateTime``, not a string) and the one date the record is
anchored to. ``category`` splits the approved scope (``general`` / ``obstetric``)
and an obstetric record may cite the gestation it annotates (nullable
``pregnancy_id``), same-patient only (cross-patient → 422).

Covered here: create a general record; create an obstetric record linked to the
episode; reject a cross-patient episode link (422); reject a gestation on a
general record (422); the listing ordered by ``occurred_at`` desc; the category
filter; and the edit/delete round trip.
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.user import User

EMAIL = "ob5@test.com"
PASSWORD = "Pass1!"


async def _setup(db: AsyncSession):
    u = User(
        email=EMAIL, hashed_password=hash_password(PASSWORD), role="user",
        is_active=True, first_name="O", last_name="B5",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Enfermaria", created_by=u.id)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PatientAccess(patient_id=p.id, user_id=u.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return u, p


async def _other_patient(db: AsyncSession, owner: User) -> Patient:
    other = Patient(given_name="Other", family_name="Person", created_by=owner.id)
    db.add(other)
    await db.commit()
    await db.refresh(other)
    db.add(PatientAccess(patient_id=other.id, user_id=owner.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return other


async def _auth(client: AsyncClient) -> dict:
    r = await client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _pregnancy(client: AsyncClient, auth: dict, pid, lmp: str = "2026-01-01") -> str:
    r = await client.post(f"/api/patients/{pid}/pregnancies", headers=auth, json={"lmp_date": lmp})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_create_general_nursing_record(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)

    assert (await client.get(f"/api/patients/{p.id}/nursing-care", headers=auth)).json() == []

    created = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={
            "occurred_at": "2026-09-01T08:30:00-03:00",
            "category": "general",
            "notes": "Administrada medicação; paciente estável.",
            "performed_by": "Enf. Souza",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category"] == "general"
    assert body["pregnancy_id"] is None
    assert body["notes"] == "Administrada medicação; paciente estável."
    assert body["performed_by"] == "Enf. Souza"
    # The record keeps the instant it refers to (Sao Paulo local ISO on the wire).
    assert body["occurred_at"].startswith("2026-09-01T08:30:00")
    rid = body["id"]

    listed = await client.get(f"/api/patients/{p.id}/nursing-care", headers=auth)
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [rid]

    single = await client.get(f"/api/nursing-care/{rid}", headers=auth)
    assert single.status_code == 200
    assert single.json()["performed_by"] == "Enf. Souza"

    patched = await client.patch(
        f"/api/nursing-care/{rid}", headers=auth, json={"performed_by": "Enf. Lima"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["performed_by"] == "Enf. Lima"

    deleted = await client.delete(f"/api/nursing-care/{rid}", headers=auth)
    assert deleted.status_code == 204
    assert (await client.get(f"/api/nursing-care/{rid}", headers=auth)).status_code == 404


async def test_create_obstetric_record_linked_to_pregnancy(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    created = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={
            "occurred_at": "2026-09-10T14:00:00-03:00",
            "category": "obstetric",
            "pregnancy_id": preg,
            "notes": "Orientação sobre amamentação.",
            "performed_by": "Enf. Alves",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category"] == "obstetric"
    assert body["pregnancy_id"] == preg

    listed = await client.get(f"/api/patients/{p.id}/nursing-care", headers=auth)
    assert listed.json()[0]["pregnancy_id"] == preg


async def test_obstetric_record_rejects_cross_patient_pregnancy(
    client: AsyncClient, db: AsyncSession
) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    other = await _other_patient(db, owner)
    foreign_preg = await _pregnancy(client, auth, other.id)

    # p is the record's patient; citing `other`'s episode is a 422, not a silent
    # cross-patient write.
    r = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={
            "occurred_at": "2026-09-10T14:00:00-03:00",
            "category": "obstetric",
            "pregnancy_id": foreign_preg,
        },
    )
    assert r.status_code == 422, r.text


async def test_general_record_rejects_pregnancy_link(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    r = await client.post(
        f"/api/patients/{p.id}/nursing-care",
        headers=auth,
        json={
            "occurred_at": "2026-09-10T14:00:00-03:00",
            "category": "general",
            "pregnancy_id": preg,
        },
    )
    assert r.status_code == 422, r.text


async def test_list_ordered_by_occurred_at_desc_and_filtered(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    for occurred_at, category, extra in [
        ("2026-08-01T09:00:00-03:00", "general", {}),
        ("2026-09-15T09:00:00-03:00", "obstetric", {"pregnancy_id": preg}),
        ("2026-09-05T09:00:00-03:00", "general", {}),
    ]:
        r = await client.post(
            f"/api/patients/{p.id}/nursing-care",
            headers=auth,
            json={"occurred_at": occurred_at, "category": category, **extra},
        )
        assert r.status_code == 201, r.text

    listing = (await client.get(f"/api/patients/{p.id}/nursing-care", headers=auth)).json()
    # Newest care first — the timeline reads by when the care occurred.
    assert [r["occurred_at"][:10] for r in listing] == ["2026-09-15", "2026-09-05", "2026-08-01"]

    only_general = (
        await client.get(f"/api/patients/{p.id}/nursing-care?category=general", headers=auth)
    ).json()
    assert [r["occurred_at"][:10] for r in only_general] == ["2026-09-05", "2026-08-01"]
    assert all(r["category"] == "general" for r in only_general)

    only_obstetric = (
        await client.get(f"/api/patients/{p.id}/nursing-care?category=obstetric", headers=auth)
    ).json()
    assert [r["pregnancy_id"] for r in only_obstetric] == [preg]
