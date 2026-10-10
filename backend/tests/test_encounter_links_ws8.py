"""WS-8: encounter_id links — a prescription and an exam (DocumentReference) can
be attributed to the consultation in which they were made/interpreted.

Covers:
* ``POST /api/encounters/{id}/link`` linking a prescription and an exam;
* the same endpoint un-linking (``/unlink``);
* the linked resources read back on the ``EncounterDto`` (``prescriptions`` /
  ``exams``);
* cross-patient links rejected with 422 (never linked silently);
* creating a prescription from a consultation sets the link, and refuses a
  consultation that belongs to another patient (422).
"""

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.document import DocumentReference
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionStatus,
)
from app.models.user import User

EMAIL = "ws8@test.com"
PASSWORD = "Pass1!"
STRANGER_EMAIL = "ws8-stranger@test.com"


async def _setup(db: AsyncSession):
    owner = User(
        email=EMAIL, hashed_password=hash_password(PASSWORD), role="user",
        is_active=True, first_name="W", last_name="Eight",
    )
    db.add(owner)
    await db.commit()
    await db.refresh(owner)

    db.add(
        Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            user_id=owner.id,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name="Test", family_name="Doctor",
        )
    )
    await db.commit()

    patient = Patient(given_name="Ana", family_name="Links", created_by=owner.id)
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    db.add(PatientAccess(patient_id=patient.id, user_id=owner.id, access_level="admin",
                         granted_at=datetime.now(UTC)))
    await db.commit()
    return owner, patient


async def _other_patient(db: AsyncSession, owner: User) -> Patient:
    other = Patient(given_name="Other", family_name="Person", created_by=owner.id)
    db.add(other)
    await db.commit()
    await db.refresh(other)
    return other


async def _auth(client: AsyncClient, email: str = EMAIL) -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _encounter(client: AsyncClient, pid, auth: dict) -> dict:
    r = await client.post(
        f"/api/patients/{pid}/encounters",
        json={"encounter_date": "2026-10-08T09:30:00", "plan": "revisar exames"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _prescription(db: AsyncSession, patient: Patient, owner: User) -> Prescription:
    rx = Prescription(
        patient_id=patient.id, prescriber_id=PRESCRIBER_SINGLETON_ID,
        owner_id=owner.id, status=PrescriptionStatus.draft, version=1,
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)
    return rx


async def _document(db: AsyncSession, patient: Patient, owner: User) -> DocumentReference:
    doc = DocumentReference(
        patient_id=patient.id, owner_id=owner.id, file_name="hemograma.pdf",
        type="lab_report", description="Hemograma completo",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# --- link / unlink a prescription ------------------------------------------


async def test_link_prescription_to_encounter(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    rx = await _prescription(db, p, owner)

    assert enc["prescriptions"] == []

    r = await client.post(
        f"/api/encounters/{enc['id']}/link", json={"prescription_id": str(rx.id)}, headers=auth
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["id"] for x in body["prescriptions"]] == [str(rx.id)]

    # the prescription now names its consultation
    got = (await client.get(f"/api/prescriptions/{rx.id}", headers=auth)).json()
    assert got["encounter_id"] == enc["id"]

    # and re-reads on the consultation
    again = (await client.get(f"/api/encounters/{enc['id']}", headers=auth)).json()
    assert [x["id"] for x in again["prescriptions"]] == [str(rx.id)]


async def test_unlink_prescription(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    rx = await _prescription(db, p, owner)

    await client.post(
        f"/api/encounters/{enc['id']}/link", json={"prescription_id": str(rx.id)}, headers=auth
    )
    r = await client.post(
        f"/api/encounters/{enc['id']}/unlink", json={"prescription_id": str(rx.id)}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["prescriptions"] == []
    got = (await client.get(f"/api/prescriptions/{rx.id}", headers=auth)).json()
    assert got["encounter_id"] is None


# --- link / unlink an exam (DocumentReference) -----------------------------


async def test_link_exam_to_encounter(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    doc = await _document(db, p, owner)

    assert enc["exams"] == []

    r = await client.post(
        f"/api/encounters/{enc['id']}/link", json={"document_id": str(doc.id)}, headers=auth
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [x["id"] for x in body["exams"]] == [str(doc.id)]
    assert body["exams"][0]["description"] == "Hemograma completo"

    got = (await client.get(f"/api/documents/{doc.id}", headers=auth)).json()
    assert got["encounter_id"] == enc["id"]

    r = await client.post(
        f"/api/encounters/{enc['id']}/unlink", json={"document_id": str(doc.id)}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["exams"] == []


# --- cross-patient links are rejected --------------------------------------


async def test_link_rejects_cross_patient_prescription(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    other = await _other_patient(db, owner)
    foreign_rx = await _prescription(db, other, owner)

    r = await client.post(
        f"/api/encounters/{enc['id']}/link",
        json={"prescription_id": str(foreign_rx.id)}, headers=auth,
    )
    assert r.status_code == 422, r.text
    # the foreign prescription is untouched
    assert foreign_rx.encounter_id is None


async def test_link_rejects_cross_patient_document(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    other = await _other_patient(db, owner)
    foreign_doc = await _document(db, other, owner)

    r = await client.post(
        f"/api/encounters/{enc['id']}/link",
        json={"document_id": str(foreign_doc.id)}, headers=auth,
    )
    assert r.status_code == 422, r.text
    assert foreign_doc.encounter_id is None


async def test_link_request_requires_exactly_one_target(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)

    r = await client.post(f"/api/encounters/{enc['id']}/link", json={}, headers=auth)
    assert r.status_code == 422, r.text

    r = await client.post(
        f"/api/encounters/{enc['id']}/link",
        json={"prescription_id": str(uuid.uuid4()), "document_id": str(uuid.uuid4())},
        headers=auth,
    )
    assert r.status_code == 422, r.text


# --- creating a prescription from a consultation ---------------------------


async def test_create_prescription_from_encounter_sets_link(client: AsyncClient, db: AsyncSession):
    _, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)

    r = await client.post(
        f"/api/patients/{p.id}/prescriptions?encounter_id={enc['id']}", headers=auth
    )
    assert r.status_code == 201, r.text
    rx = r.json()
    assert rx["encounter_id"] == enc["id"]

    got = (await client.get(f"/api/encounters/{enc['id']}", headers=auth)).json()
    assert [x["id"] for x in got["prescriptions"]] == [rx["id"]]


async def test_create_prescription_from_other_patient_encounter_rejected(
    client: AsyncClient, db: AsyncSession
):
    owner, p = await _setup(db)
    auth = await _auth(client)
    other = await _other_patient(db, owner)
    foreign_enc = Encounter(patient_id=other.id, owner_id=owner.id)
    db.add(foreign_enc)
    await db.commit()
    await db.refresh(foreign_enc)

    r = await client.post(
        f"/api/patients/{p.id}/prescriptions?encounter_id={foreign_enc.id}", headers=auth
    )
    assert r.status_code == 422, r.text


# --- access control --------------------------------------------------------


async def test_link_requires_patient_access(client: AsyncClient, db: AsyncSession):
    owner, p = await _setup(db)
    auth = await _auth(client)
    enc = await _encounter(client, p.id, auth)
    doc = await _document(db, p, owner)

    db.add(
        User(email=STRANGER_EMAIL, hashed_password=hash_password(PASSWORD), role="user",
             is_active=True, first_name="S", last_name="Tranger")
    )
    await db.commit()
    h = await _auth(client, STRANGER_EMAIL)

    r = await client.post(
        f"/api/encounters/{enc['id']}/link", json={"document_id": str(doc.id)}, headers=h
    )
    assert r.status_code in (403, 404), r.text
