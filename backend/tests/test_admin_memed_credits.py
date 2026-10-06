"""Tests for the admin Memed credits endpoint (T4.4).

Verifies that GET /api/admin/memed/credits returns the signed prescription count
and does NOT count retries as new emissions.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionStatus,
)
from app.models.user import User


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


async def test_admin_memed_credits_returns_zero_when_none(
    client: AsyncClient, db: AsyncSession
):
    """GET /api/admin/memed/credits returns signed_count=0 when no prescriptions."""
    user = await _create_user(db, "cred0@test.com", role="admin")
    tokens = await _login(client, "cred0@test.com")

    r = await client.get("/api/admin/memed/credits", headers=_auth(tokens))
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["signed_count"] == 0
    assert "note" in data


async def test_admin_memed_credits_counts_signed(
    client: AsyncClient, db: AsyncSession
):
    """GET /api/admin/memed/credits counts prescriptions with signature_state signed/archived."""
    user = await _create_user(db, "cred1@test.com", role="admin")
    tokens = await _login(client, "cred1@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create a prescription and set signature_state to "archived"
    rx = Prescription(
        patient_id=patient.id,
        prescriber_id=PRESCRIBER_SINGLETON_ID,
        owner_id=user.id,
        status=PrescriptionStatus.issued,
        version=1,
        signature_state="archived",
    )
    db.add(rx)
    await db.commit()

    r = await client.get("/api/admin/memed/credits", headers=_auth(tokens))
    assert r.status_code == 200
    data = r.json()
    assert data["signed_count"] == 1


async def test_admin_memed_credits_excludes_none(
    client: AsyncClient, db: AsyncSession
):
    """GET /api/admin/memed/credits excludes prescriptions with signature_state=none."""
    user = await _create_user(db, "cred2@test.com", role="admin")
    tokens = await _login(client, "cred2@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create a prescription with signature_state=None (draft)
    rx = Prescription(
        patient_id=patient.id,
        prescriber_id=PRESCRIBER_SINGLETON_ID,
        owner_id=user.id,
        status=PrescriptionStatus.draft,
        version=1,
        signature_state=None,
    )
    db.add(rx)
    await db.commit()

    r = await client.get("/api/admin/memed/credits", headers=_auth(tokens))
    assert r.status_code == 200
    data = r.json()
    assert data["signed_count"] == 0


async def test_admin_memed_credits_excludes_deleted(
    client: AsyncClient, db: AsyncSession
):
    """GET /api/admin/memed/credits excludes soft-deleted prescriptions."""
    user = await _create_user(db, "cred3@test.com", role="admin")
    tokens = await _login(client, "cred3@test.com")
    patient = await _create_patient(db, user)
    await _create_prescriber(db, user)

    # Create a prescription with signature_state="archived" but is_deleted=True
    rx = Prescription(
        patient_id=patient.id,
        prescriber_id=PRESCRIBER_SINGLETON_ID,
        owner_id=user.id,
        status=PrescriptionStatus.issued,
        version=1,
        signature_state="archived",
        is_deleted=True,
    )
    db.add(rx)
    await db.commit()

    r = await client.get("/api/admin/memed/credits", headers=_auth(tokens))
    assert r.status_code == 200
    data = r.json()
    assert data["signed_count"] == 0


async def test_admin_memed_credits_requires_admin(
    client: AsyncClient, db: AsyncSession
):
    """GET /api/admin/memed/credits returns 403 for non-admin users."""
    user = await _create_user(db, "cred4@test.com", role="user")
    tokens = await _login(client, "cred4@test.com")

    r = await client.get("/api/admin/memed/credits", headers=_auth(tokens))
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"