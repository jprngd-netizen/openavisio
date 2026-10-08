"""Tests for the external prescription-PDF attach endpoint.

The physician uploads a prescription PDF produced OUTSIDE OpenAvisio (e.g.
downloaded from Memed's own web app) and the backend archives it encrypted
per-patient, reusing the ``PrescriptionDocument`` infrastructure.

No network, no Memed client — this path never touches the partner API.
"""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.patient_keys import get_patient_kek
from app.core.encryption import decrypt_document
from app.core.security import hash_password
from app.core.storage import get_storage
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    PrescriptionDocument,
)
from app.models.user import User

# A tiny but structurally valid PDF payload (starts with the %PDF- magic).
PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


# ---------------------------------------------------------------------------
# Helpers (mirror test_prescription_api.py)
# ---------------------------------------------------------------------------


async def _create_user(
    db: AsyncSession, email: str, role: str = "admin", password: str = "Password1!"
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, email: str, password: str = "Password1!") -> dict:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(created_by=owner.id, given_name="Test", family_name="Patient")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(
        PatientAccess(
            patient_id=p.id,
            user_id=owner.id,
            access_level="admin",
            granted_by_user_id=owner.id,
            granted_at=datetime.now(UTC),
        )
    )
    await db.commit()
    return p


async def _create_prescriber(db: AsyncSession, user: User) -> Prescriber:
    p = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        user_id=user.id,
        external_id=str(PRESCRIBER_SINGLETON_ID),
        given_name="Test",
        family_name="Doctor",
        board_code="CRM",
        board_number="12345",
        board_state="SP",
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_attach_pdf_stores_encrypted_and_returns_issued(
    client: AsyncClient, db: AsyncSession
):
    """A valid PDF attaches, the prescription is issued, and the blob is encrypted."""
    user = await _create_user(db, "attach_ok@test.com")
    tokens = await _login(client, "attach_ok@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions/attach",
        headers=_auth(tokens),
        files={"file": ("receita.pdf", PDF_BYTES, "application/pdf")},
        data={"notes": "Receita externa (Memed web)"},
    )
    assert r.status_code in (200, 201), f"Attach failed: {r.text}"
    dto = r.json()
    assert dto["status"] == "issued"
    assert dto["signature_state"] == "external"
    assert dto["issued_at"] is not None
    assert dto["notes"] == "Receita externa (Memed web)"
    assert dto["document"] is not None
    assert dto["document"]["signed"] is False
    assert dto["document"]["memed_prescription_id"] is None
    assert dto["document"]["file_name"] == "receita.pdf"

    rx_id = dto["id"]

    # The blob in storage is encrypted (never the plaintext PDF) ...
    doc_row = (
        await db.execute(
            select(PrescriptionDocument).where(
                PrescriptionDocument.prescription_id == rx_id
            )
        )
    ).scalar_one()
    assert doc_row.storage_path == f"{patient.id}/{doc_row.id}.enc"
    ciphertext = get_storage().read(doc_row.storage_path)
    assert b"%PDF" not in ciphertext, "Storage must hold ciphertext, not plaintext"

    # ... and decrypts back to the exact uploaded bytes.
    kek = await get_patient_kek(db, patient.id)
    assert decrypt_document(ciphertext, doc_row.encrypted_dek, kek) == PDF_BYTES

    # GET /document streams the exact original bytes.
    r = await client.get(
        f"/api/prescriptions/{rx_id}/document",
        headers=_auth(tokens),
    )
    assert r.status_code == 200, f"Download failed: {r.text}"
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == PDF_BYTES


async def test_attach_rejects_non_pdf(client: AsyncClient, db: AsyncSession):
    """A non-PDF upload is rejected with 400 and nothing is archived."""
    user = await _create_user(db, "attach_bad@test.com")
    tokens = await _login(client, "attach_bad@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions/attach",
        headers=_auth(tokens),
        files={"file": ("nota.txt", b"hello, not a pdf", "text/plain")},
    )
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
    assert r.json()["detail"]["code"] == "invalid_pdf"

    # No prescription was created.
    from app.models.prescription import Prescription

    docs = (
        await db.execute(
            select(Prescription).where(Prescription.patient_id == patient.id)
        )
    ).scalars().all()
    assert len(docs) == 0


async def test_attach_without_patient_access_is_rejected(
    client: AsyncClient, db: AsyncSession
):
    """A user with no patient grant cannot attach.

    ``require_patient_access`` — the same guard used by every other
    patient-scoped prescription route — returns 404 for missing/insufficient
    access, so this asserts that exact behaviour.
    """
    owner = await _create_user(db, "attach_own@test.com")
    other = await _create_user(db, "attach_other@test.com", role="user")
    patient = await _create_patient(db, owner)
    await _create_prescriber(db, owner)

    tokens = await _login(client, "attach_other@test.com")
    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions/attach",
        headers=_auth(tokens),
        files={"file": ("receita.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code in (403, 404), f"Expected access denial, got {r.status_code}: {r.text}"


async def test_attach_without_prescriber_is_409(client: AsyncClient, db: AsyncSession):
    """Without a configured prescriber, attach returns 409."""
    user = await _create_user(db, "attach_nop@test.com")
    tokens = await _login(client, "attach_nop@test.com")
    patient = await _create_patient(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions/attach",
        headers=_auth(tokens),
        files={"file": ("receita.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    assert r.json()["detail"]["code"] == "prescriber_not_configured"
