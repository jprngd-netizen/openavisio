"""OB-4: gestational clinical integrations.

The episode gathers its clinical evidence:

* intercorrências (DMG, pre-eclampsia, ...) as ``Condition`` rows linked to the
  ``Pregnancy`` — the Condition is found-or-created by (patient, code) through
  the WS-3 service and is **never deleted**; only the link is;
* vitals (``Observation``) and exams (``DocumentReference``) attributed to the
  episode through a nullable back-reference, exactly as WS-8 did for
  consultations.

Covered here: link/unlink an intercorrência, exam and vital; the ``PregnancyDto``
exposing the lists/counts; problem-list reuse (no duplicate Condition, no
duplicate link); and same-patient enforcement (cross-patient links → 422).
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.condition import Condition
from app.models.document import DocumentReference
from app.models.observation import Observation
from app.models.patient import Patient
from app.models.user import User

EMAIL = "ob4@test.com"
PASSWORD = "Pass1!"

DMG = {"cid10_code": "O24.4", "cid10_display": "Diabetes mellitus gestacional"}


async def _setup(db: AsyncSession):
    u = User(email=EMAIL, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="O", last_name="B4")
    db.add(u)
    await db.commit()
    await db.refresh(u)
    p = Patient(given_name="Ana", family_name="Gestante", created_by=u.id)
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
    # The owner has access to both patients (as when two records are created by
    # the same user) — so a cross-patient link hits the 422, not access control.
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


async def _observation(db: AsyncSession, patient: Patient, owner: User) -> Observation:
    obs = Observation(
        patient_id=patient.id, owner_id=owner.id, category="measurement",
        code="body-weight", code_display="Weight", value_quantity=64.0, value_unit="kg",
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)
    return obs


async def _document(db: AsyncSession, patient: Patient, owner: User) -> DocumentReference:
    doc = DocumentReference(
        patient_id=patient.id, owner_id=owner.id, file_name="hemograma.pdf",
        type="lab_report", description="Hemograma completo",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# --- intercorrências as linked Conditions ----------------------------------


async def test_add_and_remove_intercorrencia_keeps_condition(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    added = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions", headers=auth, json=DMG
    )
    assert added.status_code == 201, added.text
    body = added.json()
    assert body["condition_count"] == 1
    assert len(body["conditions"]) == 1
    assert body["conditions"][0]["cid10_code"] == "O24.4"
    assert body["conditions"][0]["cid10_display"] == DMG["cid10_display"]
    cond_id = body["conditions"][0]["condition_id"]

    # The intercorrência is now part of the problem list.
    conds = (await client.get(f"/api/patients/{p.id}/conditions", headers=auth)).json()
    assert [c["id"] for c in conds] == [cond_id]
    assert conds[0]["code"] == "O24.4"

    # Readable back on the episode, both single and listing.
    single = await client.get(f"/api/pregnancies/{preg}", headers=auth)
    assert single.json()["condition_count"] == 1
    listing = await client.get(f"/api/patients/{p.id}/pregnancies", headers=auth)
    assert listing.json()[0]["condition_count"] == 1

    # Removing the intercorrência un-links it but the Condition SURVIVES.
    removed = await client.delete(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions/{cond_id}", headers=auth
    )
    assert removed.status_code == 204, removed.text
    after = (await client.get(f"/api/pregnancies/{preg}", headers=auth)).json()
    assert after["conditions"] == []
    assert after["condition_count"] == 0
    conds = (await client.get(f"/api/patients/{p.id}/conditions", headers=auth)).json()
    assert [c["id"] for c in conds] == [cond_id]


async def test_readd_reuses_condition_and_link(client: AsyncClient, db: AsyncSession) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    first = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions", headers=auth, json=DMG
    )
    cond_id = first.json()["conditions"][0]["condition_id"]

    # Re-adding the same (patient, code) does not duplicate the Condition nor
    # the link: the problem list and the episode both stay at one.
    again = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions", headers=auth, json=DMG
    )
    assert again.status_code == 201, again.text
    assert again.json()["condition_count"] == 1
    assert again.json()["conditions"][0]["condition_id"] == cond_id
    conds = (await client.get(f"/api/patients/{p.id}/conditions", headers=auth)).json()
    assert len(conds) == 1

    # After a remove, re-adding re-activates the SAME link (no second row).
    await client.delete(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions/{cond_id}", headers=auth
    )
    reactivated = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/conditions", headers=auth, json=DMG
    )
    assert reactivated.json()["condition_count"] == 1
    rows = (
        await db.execute(select(Condition).where(Condition.patient_id == p.id))
    ).scalars().all()
    assert len(rows) == 1  # the problem list never duplicated


# --- vitals and exams attributed to the episode ----------------------------


async def test_link_and_unlink_exam(client: AsyncClient, db: AsyncSession) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    doc = await _document(db, p, owner)

    assert (await client.get(f"/api/pregnancies/{preg}", headers=auth)).json()["exams"] == []

    linked = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link",
        headers=auth, json={"document_id": str(doc.id)},
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["exam_count"] == 1
    assert [x["id"] for x in body["exams"]] == [str(doc.id)]
    assert body["exams"][0]["description"] == "Hemograma completo"

    # The exam now names its gestation.
    got = (await client.get(f"/api/documents/{doc.id}", headers=auth)).json()
    assert got["pregnancy_id"] == preg

    unlinked = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/unlink",
        headers=auth, json={"document_id": str(doc.id)},
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["exams"] == []
    got = (await client.get(f"/api/documents/{doc.id}", headers=auth)).json()
    assert got["pregnancy_id"] is None


async def test_link_and_unlink_vital(client: AsyncClient, db: AsyncSession) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    obs = await _observation(db, p, owner)

    assert (await client.get(f"/api/pregnancies/{preg}", headers=auth)).json()["vitals"] == []

    linked = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link",
        headers=auth, json={"observation_id": str(obs.id)},
    )
    assert linked.status_code == 200, linked.text
    body = linked.json()
    assert body["vital_count"] == 1
    assert [v["id"] for v in body["vitals"]] == [str(obs.id)]

    await db.refresh(obs)
    assert obs.pregnancy_id is not None

    unlinked = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/unlink",
        headers=auth, json={"observation_id": str(obs.id)},
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["vitals"] == []
    await db.refresh(obs)
    assert obs.pregnancy_id is None


# --- same-patient enforcement ----------------------------------------------


async def test_link_rejects_cross_patient_exam(client: AsyncClient, db: AsyncSession) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    other = await _other_patient(db, owner)
    foreign_doc = await _document(db, other, owner)

    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link",
        headers=auth, json={"document_id": str(foreign_doc.id)},
    )
    assert r.status_code == 422, r.text
    assert foreign_doc.pregnancy_id is None


async def test_link_rejects_cross_patient_vital(client: AsyncClient, db: AsyncSession) -> None:
    owner, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    other = await _other_patient(db, owner)
    foreign_obs = await _observation(db, other, owner)

    r = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link",
        headers=auth, json={"observation_id": str(foreign_obs.id)},
    )
    assert r.status_code == 422, r.text
    assert foreign_obs.pregnancy_id is None


async def test_condition_rejects_cross_patient_pregnancy(
    client: AsyncClient, db: AsyncSession
) -> None:
    u, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)
    other = await _other_patient(db, u)

    # p is the episode's patient; recording the intercorrência under `other` is 422.
    r = await client.post(
        f"/api/patients/{other.id}/pregnancies/{preg}/conditions", headers=auth, json=DMG
    )
    assert r.status_code == 422, r.text


async def test_link_request_requires_exactly_one_target(
    client: AsyncClient, db: AsyncSession
) -> None:
    _, p = await _setup(db)
    auth = await _auth(client)
    preg = await _pregnancy(client, auth, p.id)

    empty = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link", headers=auth, json={}
    )
    assert empty.status_code == 422, empty.text

    both = await client.post(
        f"/api/patients/{p.id}/pregnancies/{preg}/link",
        headers=auth,
        json={
            "observation_id": "00000000-0000-0000-0000-000000000000",
            "document_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert both.status_code == 422, both.text
