"""Tests for deployment_mode and memed_emission_policy config fields.

T5.1 — deployment_mode: personal (default, implemented), clinic/multi_tenant fail.
T5.2 — memed_emission_policy: linked_user (default), any_admin accepted, others rejected.
T5.3 — Extension hooks (terms_url, telemetry_enabled) — fields only, no wiring.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password
from app.deps import get_memed_client
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionStatus,
)
from app.models.user import User
from app.services.prescriptions.fakes import FakeMemedClient


def _settings(**kwargs) -> Settings:
    """Build a Settings instance with dev defaults (no production guard)."""
    defaults = dict(environment="development")
    defaults.update(kwargs)
    return Settings(**defaults, _env_file=None)


# ---------------------------------------------------------------------------
# Helpers (mirrored from test_prescription_api to keep this file self-contained)
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
# Config field tests
# ---------------------------------------------------------------------------


class TestDeploymentMode:
    """T5.1 — deployment_mode field."""

    def test_default_is_personal(self):
        s = _settings()
        assert s.deployment_mode == "personal"

    def test_personal_passes(self):
        s = _settings(deployment_mode="personal")
        assert s.deployment_mode == "personal"

    def test_clinic_fails(self):
        with pytest.raises(ValueError, match="not yet implemented|DEPLOYMENT_MODE"):
            _settings(deployment_mode="clinic")

    def test_multi_tenant_fails(self):
        with pytest.raises(ValueError, match="not yet implemented|DEPLOYMENT_MODE"):
            _settings(deployment_mode="multi_tenant")

    def test_invalid_mode_fails(self):
        with pytest.raises(ValueError, match="DEPLOYMENT_MODE"):
            _settings(deployment_mode="bogus")


class TestEmissionPolicy:
    """T5.2 — memed_emission_policy field."""

    def test_default_is_linked_user(self):
        s = _settings()
        assert s.memed_emission_policy == "linked_user"

    def test_linked_user_passes(self):
        s = _settings(memed_emission_policy="linked_user")
        assert s.memed_emission_policy == "linked_user"

    def test_any_admin_passes(self):
        s = _settings(memed_emission_policy="any_admin")
        assert s.memed_emission_policy == "any_admin"

    def test_invalid_policy_fails(self):
        with pytest.raises(ValueError, match="MEMED_EMISSION_POLICY"):
            _settings(memed_emission_policy="invalid")


class TestExtensionHooks:
    """T5.3 — Extension hooks (terms/telemetry), OFF by default."""

    def test_terms_url_defaults_to_empty(self):
        s = _settings()
        assert s.terms_url == ""

    def test_telemetry_enabled_defaults_to_false(self):
        s = _settings()
        assert s.telemetry_enabled is False


# ---------------------------------------------------------------------------
# T5.2 — Emission policy gate behaviour
# ---------------------------------------------------------------------------


class TestEmissionPolicyGate:
    """Behavioural tests for the emission policy gate in _require_prescriber_user."""

    async def test_linked_user_default_blocks_non_prescriber(
        self, client: AsyncClient, db: AsyncSession
    ):
        """Default linked_user blocks a non-prescriber user from capturing."""
        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        try:
            admin_user = await _create_user(db, "epg_adm@test.com", role="admin")
            other_user = await _create_user(db, "epg_oth@test.com", role="user")
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

            tokens = await _login(client, "epg_oth@test.com")

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
                json={"prescription_id": "memed-epg-1", "signed": True},
                headers=_auth(tokens),
            )
            assert r.status_code == 403, (
                f"Expected 403 with default linked_user, "
                f"got {r.status_code}: {r.text}"
            )
        finally:
            app.dependency_overrides.pop(get_memed_client, None)

    async def test_any_admin_allows_any_admin_to_emit(
        self, client: AsyncClient, db: AsyncSession
    ):
        """With memed_emission_policy=any_admin, any admin can emit."""
        from app.core.config import settings

        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        original_policy = settings.memed_emission_policy
        settings.memed_emission_policy = "any_admin"

        try:
            admin_user = await _create_user(db, "epg_adm2@test.com", role="admin")
            other_admin = await _create_user(db, "epg_oth_adm@test.com", role="admin")
            patient = await _create_patient(db, admin_user)
            await _create_prescriber(db, admin_user)

            # Give other_admin access to the patient
            db.add(
                PatientAccess(
                    patient_id=patient.id,
                    user_id=other_admin.id,
                    access_level="contribute",
                    granted_by_user_id=admin_user.id,
                    granted_at=datetime.now(UTC),
                )
            )
            await db.commit()

            tokens = await _login(client, "epg_oth_adm@test.com")

            # Create draft as other_admin
            r = await client.post(
                f"/api/patients/{patient.id}/prescriptions",
                headers=_auth(tokens),
            )
            assert r.status_code == 201
            rx_id = r.json()["id"]

            # Capture as other_admin (not the linked prescriber user)
            r = await client.post(
                f"/api/prescriptions/{rx_id}/capture",
                json={"prescription_id": "memed-epg-2", "signed": True},
                headers=_auth(tokens),
            )
            assert r.status_code == 200, (
                f"Expected 200 with any_admin policy, "
                f"got {r.status_code}: {r.text}"
            )
        finally:
            settings.memed_emission_policy = original_policy
            app.dependency_overrides.pop(get_memed_client, None)

    async def test_any_admin_still_blocks_non_admin(
        self, client: AsyncClient, db: AsyncSession
    ):
        """With any_admin, a non-admin user is still blocked."""
        from app.core.config import settings

        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        original_policy = settings.memed_emission_policy
        settings.memed_emission_policy = "any_admin"

        try:
            admin_user = await _create_user(db, "epg_adm3@test.com", role="admin")
            regular_user = await _create_user(db, "epg_reg@test.com", role="user")
            patient = await _create_patient(db, admin_user)
            await _create_prescriber(db, admin_user)

            # Give regular_user access to the patient
            db.add(
                PatientAccess(
                    patient_id=patient.id,
                    user_id=regular_user.id,
                    access_level="contribute",
                    granted_by_user_id=admin_user.id,
                    granted_at=datetime.now(UTC),
                )
            )
            await db.commit()

            tokens = await _login(client, "epg_reg@test.com")

            # Create draft as regular_user
            r = await client.post(
                f"/api/patients/{patient.id}/prescriptions",
                headers=_auth(tokens),
            )
            assert r.status_code == 201
            rx_id = r.json()["id"]

            # Try to capture as regular_user (not admin)
            r = await client.post(
                f"/api/prescriptions/{rx_id}/capture",
                json={"prescription_id": "memed-epg-3", "signed": True},
                headers=_auth(tokens),
            )
            assert r.status_code == 403, (
                f"Expected 403 with any_admin for non-admin, "
                f"got {r.status_code}: {r.text}"
            )
        finally:
            settings.memed_emission_policy = original_policy
            app.dependency_overrides.pop(get_memed_client, None)