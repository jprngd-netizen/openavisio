"""Tests for the Prescription and Prescriber API endpoints.

Covers the full prescription lifecycle: create draft, autosave with versioned
concurrency, capture via FakeMemedClient, access control, PDF download, and
admin prescriber CPF masking.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_str
from app.core.patient_keys import ensure_patient_kek
from app.core.security import hash_password
from app.deps import get_memed_client
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionDocument,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.models.user import User
from app.services.prescriptions.fakes import FakeMemedClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(
    db: AsyncSession,
    email: str,
    role: str = "user",
    password: str = "Password1!",
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


async def _create_patient(
    db: AsyncSession,
    owner: User,
    given: str = "Test",
    family: str = "Patient",
) -> Patient:
    p = Patient(created_by=owner.id, given_name=given, family_name=family)
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


async def test_create_draft_and_autosave_increments_version(client: AsyncClient, db: AsyncSession):
    """Create draft → autosave increments version."""
    user = await _create_user(db, "rx_ver@test.com", role="admin")
    tokens = await _login(client, "rx_ver@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create draft
    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 201, f"Create failed: {r.text}"
    rx = r.json()
    assert rx["status"] == "draft"
    assert rx["version"] == 1
    rx_id = rx["id"]

    # Autosave with items
    r = await client.patch(
        f"/api/prescriptions/{rx_id}",
        json={
            "version": 1,
            "items": [
                {
                    "medication_name": "Paracetamol",
                    "posology": "1 comprimido 8/8h",
                    "quantity": "30",
                }
            ],
        },
        headers=_auth(tokens),
    )
    assert r.status_code == 200, f"Autosave failed: {r.text}"
    rx2 = r.json()
    assert rx2["version"] == 2
    assert len(rx2["items"]) == 1
    assert rx2["items"][0]["medication_name"] == "Paracetamol"


async def test_stale_autosave_returns_409(client: AsyncClient, db: AsyncSession):
    """Stale autosave returns 409 with current_version."""
    user = await _create_user(db, "rx_stale@test.com", role="admin")
    tokens = await _login(client, "rx_stale@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create draft
    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 201
    rx_id = r.json()["id"]

    # Update once (version becomes 2)
    r = await client.patch(
        f"/api/prescriptions/{rx_id}",
        json={"version": 1, "notes": "first update"},
        headers=_auth(tokens),
    )
    assert r.status_code == 200

    # Try to update with stale version 1
    r = await client.patch(
        f"/api/prescriptions/{rx_id}",
        json={"version": 1, "notes": "stale update"},
        headers=_auth(tokens),
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert detail["code"] == "stale_version"
    assert detail["current_version"] == 2


async def test_capture_with_fake_produces_issued(client: AsyncClient, db: AsyncSession):
    """Capture with fake produces issued + PrescriptionDocument."""
    fake = FakeMemedClient()
    app = client._transport.app
    app.dependency_overrides[get_memed_client] = lambda: fake

    try:
        user = await _create_user(db, "rx_cap@test.com", role="admin")
        tokens = await _login(client, "rx_cap@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        # Create draft
        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = r.json()["id"]

        # Capture
        r = await client.post(
            f"/api/prescriptions/{rx_id}/capture",
            json={"prescription_id": "memed-123", "signed": True},
            headers=_auth(tokens),
        )
        assert r.status_code == 200, f"Capture failed: {r.text}"
        result = r.json()
        assert result["status"] == "issued"
        assert result["document"] is not None
        assert result["document"]["file_name"] is not None
    finally:
        app.dependency_overrides.pop(get_memed_client, None)


async def test_user_without_grant_gets_404(client: AsyncClient, db: AsyncSession):
    """User without grant gets 404."""
    owner = await _create_user(db, "rx_own@test.com", role="admin")
    other = await _create_user(db, "rx_oth@test.com", role="user")
    patient = await _create_patient(db, owner)

    tokens = await _login(client, "rx_oth@test.com")
    r = await client.get(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 404


async def test_non_prescriber_gets_403_on_capture(client: AsyncClient, db: AsyncSession):
    """Non-prescriber gets 403 on capture."""
    fake = FakeMemedClient()
    app = client._transport.app
    app.dependency_overrides[get_memed_client] = lambda: fake

    try:
        admin_user = await _create_user(db, "rx_adm@test.com", role="admin")
        other_user = await _create_user(db, "rx_oth2@test.com", role="user")
        patient = await _create_patient(db, admin_user)
        await _create_prescriber(db, admin_user)

        # Give other_user access to the patient
        db.add(
            PatientAccess(
                patient_id=patient.id,
                user_id=other_user.id,
                access_level="contribute",
                granted_by_user_id=admin_user.id,
                granted_at=datetime.now(UTC),
            )
        )
        await db.commit()

        tokens = await _login(client, "rx_oth2@test.com")

        # Create draft as other_user
        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = r.json()["id"]

        # Try to capture as other_user (not the prescriber)
        r = await client.post(
            f"/api/prescriptions/{rx_id}/capture",
            json={"prescription_id": "memed-456", "signed": True},
            headers=_auth(tokens),
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    finally:
        app.dependency_overrides.pop(get_memed_client, None)


async def test_get_document_returns_pdf(client: AsyncClient, db: AsyncSession):
    """GET /document returns the PDF."""
    fake = FakeMemedClient()
    app = client._transport.app
    app.dependency_overrides[get_memed_client] = lambda: fake

    try:
        user = await _create_user(db, "rx_doc@test.com", role="admin")
        tokens = await _login(client, "rx_doc@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        # Create and capture
        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = r.json()["id"]

        r = await client.post(
            f"/api/prescriptions/{rx_id}/capture",
            json={"prescription_id": "memed-789", "signed": True},
            headers=_auth(tokens),
        )
        assert r.status_code == 200, f"Capture failed: {r.text}"

        # Get document
        r = await client.get(
            f"/api/prescriptions/{rx_id}/document",
            headers=_auth(tokens),
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
    finally:
        app.dependency_overrides.pop(get_memed_client, None)


async def test_admin_prescriber_no_full_cpf(client: AsyncClient, db: AsyncSession):
    """GET /admin/prescriber does NOT contain the full CPF."""
    user = await _create_user(db, "rx_cpf@test.com", role="admin")
    tokens = await _login(client, "rx_cpf@test.com")

    # Create prescriber with CPF
    from app.core.encryption import encrypt_setting

    p = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        user_id=user.id,
        external_id=str(PRESCRIBER_SINGLETON_ID),
        given_name="Test",
        family_name="Doctor",
        cpf_encrypted=encrypt_setting("12345678901"),
        cpf_last4="8901",
        board_code="CRM",
        board_number="12345",
        board_state="SP",
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)

    r = await client.get(
        "/api/admin/prescriber",
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    data = r.json()
    assert "cpf_encrypted" not in data, "Response must not contain cpf_encrypted"
    assert data.get("cpf_last4") == "8901"
    # The full CPF should not appear anywhere in the response
    assert "12345678901" not in json.dumps(data), "Full CPF leaked in response"


async def test_create_draft_without_prescriber_returns_409(
    client: AsyncClient, db: AsyncSession
):
    """Creating a prescription without a configured prescriber returns 409."""
    user = await _create_user(db, "rx_nop@test.com", role="admin")
    tokens = await _login(client, "rx_nop@test.com")
    patient = await _create_patient(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 409, f"Expected 409, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert detail["code"] == "prescriber_not_configured"


async def test_delete_draft_sets_is_deleted(client: AsyncClient, db: AsyncSession):
    """DELETE on a draft sets is_deleted=True."""
    user = await _create_user(db, "rx_del@test.com", role="admin")
    tokens = await _login(client, "rx_del@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create draft
    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 201
    rx_id = r.json()["id"]

    # Delete
    r = await client.delete(
        f"/api/prescriptions/{rx_id}",
        headers=_auth(tokens),
    )
    assert r.status_code == 204

    # Verify it's gone from list
    r = await client.get(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    assert len(r.json()) == 0


async def test_memed_session_returns_token(client: AsyncClient, db: AsyncSession):
    """POST /memed-session returns data-token + script URL + patient."""
    fake = FakeMemedClient()
    app = client._transport.app
    app.dependency_overrides[get_memed_client] = lambda: fake

    try:
        user = await _create_user(db, "rx_ses@test.com", role="admin")
        tokens = await _login(client, "rx_ses@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = r.json()["id"]

        r = await client.post(
            f"/api/prescriptions/{rx_id}/memed-session",
            headers=_auth(tokens),
        )
        assert r.status_code == 200, f"Session failed: {r.text}"
        data = r.json()
        assert data["data_token"] == "fake-token-001"
        assert "script_url" in data
        assert "patient" in data
        assert data["patient"]["nome"] == "Test"
        assert r.headers.get("cache-control") == "no-store"
    finally:
        app.dependency_overrides.pop(get_memed_client, None)


async def test_memed_deleted_marks_status(client: AsyncClient, db: AsyncSession):
    """POST /memed-deleted marks status=deleted."""
    user = await _create_user(db, "rx_mdel@test.com", role="admin")
    tokens = await _login(client, "rx_mdel@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 201
    rx_id = r.json()["id"]

    r = await client.post(
        f"/api/prescriptions/{rx_id}/memed-deleted",
        json={"prescription_id": "memed-999"},
        headers=_auth(tokens),
    )
    assert r.status_code == 200, f"Memed-deleted failed: {r.text}"

    # Verify status
    r = await client.get(
        f"/api/prescriptions/{rx_id}",
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


async def test_retry_failed_to_draft(client: AsyncClient, db: AsyncSession):
    """POST /retry transitions failed → draft."""
    user = await _create_user(db, "rx_ret@test.com", role="admin")
    tokens = await _login(client, "rx_ret@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    r = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 201
    rx_id = r.json()["id"]

    # Manually set to failed
    from sqlalchemy import update as sql_update
    from app.models.prescription import Prescription

    stmt = (
        sql_update(Prescription)
        .where(Prescription.id == uuid.UUID(rx_id))
        .values(status="failed")
    )
    await db.execute(stmt)
    await db.commit()

    # Retry
    r = await client.post(
        f"/api/prescriptions/{rx_id}/retry",
        headers=_auth(tokens),
    )
    assert r.status_code == 200, f"Retry failed: {r.text}"
    assert r.json()["status"] == "draft"


async def test_list_prescriptions_filters_deleted(client: AsyncClient, db: AsyncSession):
    """List prescriptions filters is_deleted=False AND status != deleted."""
    user = await _create_user(db, "rx_lst@test.com", role="admin")
    tokens = await _login(client, "rx_lst@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create two drafts
    r1 = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r2.status_code == 201

    # List should have 2
    r = await client.get(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    assert len(r.json()) == 2

    # Delete one
    rx2_id = r2.json()["id"]
    await client.delete(
        f"/api/prescriptions/{rx2_id}",
        headers=_auth(tokens),
    )

    # List should have 1
    r = await client.get(
        f"/api/patients/{patient.id}/prescriptions",
        headers=_auth(tokens),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---------------------------------------------------------------------------
# Gap 1 — patient CPF in memed-session
# ---------------------------------------------------------------------------


async def test_memed_session_includes_cpf_when_patient_has_encrypted_cpf(
    client: AsyncClient, db: AsyncSession
):
    """POST /memed-session includes CPF when patient has encrypted CPF."""
    fake = FakeMemedClient()
    app = client._transport.app
    app.dependency_overrides[get_memed_client] = lambda: fake

    try:
        user = await _create_user(db, "rx_cpf_ses@test.com", role="admin")
        tokens = await _login(client, "rx_cpf_ses@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        # Set encrypted CPF on the patient
        patient_kek = await ensure_patient_kek(db, patient.id)
        patient.cpf_encrypted = encrypt_str("12345678901", patient_kek)
        patient.cpf_last4 = "8901"
        await db.commit()

        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = r.json()["id"]

        r = await client.post(
            f"/api/prescriptions/{rx_id}/memed-session",
            headers=_auth(tokens),
        )
        assert r.status_code == 200, f"Session failed: {r.text}"
        data = r.json()
        assert data["patient"]["cpf"] == "12345678901"
    finally:
        app.dependency_overrides.pop(get_memed_client, None)


# ---------------------------------------------------------------------------
# Gap 3 — CPF required on prescriber create
# ---------------------------------------------------------------------------


async def test_admin_prescriber_create_without_cpf_returns_422(
    client: AsyncClient, db: AsyncSession
):
    """PUT /admin/prescriber without CPF on first create returns 422."""
    user = await _create_user(db, "rx_cpf_crt@test.com", role="admin")
    tokens = await _login(client, "rx_cpf_crt@test.com")

    r = await client.put(
        "/api/admin/prescriber",
        json={
            "given_name": "No",
            "family_name": "Cpf",
            "board_code": "CRM",
            "board_number": "99999",
            "board_state": "SP",
        },
        headers=_auth(tokens),
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


async def test_admin_prescriber_create_with_cpf_succeeds(
    client: AsyncClient, db: AsyncSession
):
    """PUT /admin/prescriber with CPF on create succeeds."""
    user = await _create_user(db, "rx_cpf_ok@test.com", role="admin")
    tokens = await _login(client, "rx_cpf_ok@test.com")

    r = await client.put(
        "/api/admin/prescriber",
        json={
            "given_name": "Has",
            "family_name": "Cpf",
            "cpf": "98765432109",
            "board_code": "CRM",
            "board_number": "88888",
            "board_state": "SP",
        },
        headers=_auth(tokens),
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["cpf_last4"] == "2109"
    # Full CPF must not leak
    assert "cpf_encrypted" not in data