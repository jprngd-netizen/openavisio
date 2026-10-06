"""Sentinel-based log redaction tests for the prescription domain.

All tests verify that secrets (token, CPF, unlock_code) never appear in
captured logs, repr output, or API responses.  Uses FakeMemedClient with
a known sentinel value — never touches the network.

Domain terms (see CONTEXT.md):
- Prescriber: the licensed healthcare professional authorized to issue prescriptions
- Prescription: a draft or issued medical prescription for a Patient
- PrescriptionDocument: the archived signed PDF of an issued Prescription
"""
from __future__ import annotations

import json
import logging

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_setting
from app.core.security import hash_password
from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.models.user import User
from app.services.prescriptions.fakes import FakeMemedClient
from app.services.prescriptions.ports import DigitalLinkResult, PrescriberResult
from app.services.prescriptions.prescriber import ensure_prescriber, fresh_token

SENTINEL_TOKEN = "SENTINEL-TOKEN-abc123"
SENTINEL_CPF = "12345678901"
SENTINEL_UNLOCK = "SENTINEL-UNLOCK-999999"


# ---------------------------------------------------------------------------
# Sentinel fake
# ---------------------------------------------------------------------------


class _SentinelFake(FakeMemedClient):
    """Fake that returns a known sentinel token for all prescriber operations."""

    async def get_prescriber(self, external_id: str) -> PrescriberResult:
        self._record("get_prescriber", external_id=external_id)
        return PrescriberResult(
            external_id=external_id,
            memed_user_id="usr_sentinel",
            status="Ativo",
            token=SENTINEL_TOKEN,
        )

    async def create_prescriber(self, payload: dict) -> PrescriberResult:
        self._record("create_prescriber", payload=payload)
        return PrescriberResult(
            external_id="ext-sentinel",
            memed_user_id="usr_sentinel",
            status="Ativo",
            token=SENTINEL_TOKEN,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_prescriber_in_db(db: AsyncSession) -> Prescriber:
    """Create a minimal Prescriber record in the test database."""
    prescriber = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        external_id=str(PRESCRIBER_SINGLETON_ID),
        given_name="Test",
        family_name="Doctor",
        board_code="CRM",
        board_number="12345",
        board_state="SP",
    )
    db.add(prescriber)
    await db.flush()
    return prescriber


async def _create_admin_user(db: AsyncSession) -> User:
    """Create an admin user for API tests."""
    user = User(
        email="log_redact@test.com",
        hashed_password=hash_password("Password1!"),
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient) -> dict:
    """Login as the test admin user and return token dict."""
    r = await client.post(
        "/api/auth/login",
        json={"email": "log_redact@test.com", "password": "Password1!"},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Test: repr hides secrets
# ---------------------------------------------------------------------------


class TestReprHidesSecrets:
    """repr() of result dataclasses must not contain secrets."""

    def test_prescriber_result_repr_hides_token(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token=SENTINEL_TOKEN,
        )
        r = repr(result)
        assert SENTINEL_TOKEN not in r

    def test_prescriber_result_repr_hides_cpf(self):
        result = PrescriberResult(
            external_id="ext-1",
            memed_user_id="usr_abc",
            status="Ativo",
            token="tok_xxx",
            cpf=SENTINEL_CPF,
        )
        r = repr(result)
        assert SENTINEL_CPF not in r

    def test_digital_link_result_repr_hides_unlock_code(self):
        result = DigitalLinkResult(
            link="https://memed.fake.com/r/abc123",
            unlock_code=SENTINEL_UNLOCK,
        )
        r = repr(result)
        assert SENTINEL_UNLOCK not in r


# ---------------------------------------------------------------------------
# Test: logs do not contain sentinel token after running real code
# ---------------------------------------------------------------------------


class TestLogsNoSentinel:
    """Logs captured during real prescriber operations must not contain secrets."""

    async def test_fresh_token_logs_no_sentinel(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ):
        """Call fresh_token with a sentinel-returning fake and assert no leak."""
        await _create_prescriber_in_db(db)
        fake = _SentinelFake()
        caplog.set_level(logging.DEBUG)

        token = await fresh_token(db, fake)

        assert token == SENTINEL_TOKEN, "fresh_token should return the sentinel"
        for record in caplog.records:
            assert SENTINEL_TOKEN not in record.getMessage(), (
                f"Sentinel token leaked in log at {record.name}:{record.levelname}: "
                f"{record.getMessage()}"
            )

    async def test_ensure_prescriber_logs_no_sentinel(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ):
        """Call ensure_prescriber with a sentinel-returning fake and assert no leak."""
        await _create_prescriber_in_db(db)
        fake = _SentinelFake()
        caplog.set_level(logging.DEBUG)

        result = await ensure_prescriber(db, fake)

        assert result.memed_user_id == "usr_sentinel"
        for record in caplog.records:
            assert SENTINEL_TOKEN not in record.getMessage(), (
                f"Sentinel token leaked in log at {record.name}:{record.levelname}: "
                f"{record.getMessage()}"
            )

    async def test_ensure_prescriber_create_path_logs_no_sentinel(
        self, db: AsyncSession, caplog: pytest.LogCaptureFixture
    ):
        """Call ensure_prescriber when prescriber does NOT exist on Memed (create path)."""
        await _create_prescriber_in_db(db)

        class _NotFoundThenSentinel(FakeMemedClient):
            """First get_prescriber raises (not found), then create returns sentinel."""

            def __init__(self) -> None:
                super().__init__()
                self._get_count = 0

            async def get_prescriber(self, external_id: str) -> PrescriberResult:
                self._record("get_prescriber", external_id=external_id)
                self._get_count += 1
                if self._get_count == 1:
                    raise KeyError(f"Prescriber {external_id} not found")
                return PrescriberResult(
                    external_id=external_id,
                    memed_user_id="usr_sentinel",
                    status="Ativo",
                    token=SENTINEL_TOKEN,
                )

            async def create_prescriber(self, payload: dict) -> PrescriberResult:
                self._record("create_prescriber", payload=payload)
                return PrescriberResult(
                    external_id="ext-sentinel",
                    memed_user_id="usr_sentinel",
                    status="Ativo",
                    token=SENTINEL_TOKEN,
                )

        fake = _NotFoundThenSentinel()
        caplog.set_level(logging.DEBUG)

        result = await ensure_prescriber(db, fake)

        assert result.memed_user_id == "usr_sentinel"
        # Verify create_prescriber was called
        create_calls = [c for c in fake.calls if c[0] == "create_prescriber"]
        assert len(create_calls) == 1
        for record in caplog.records:
            assert SENTINEL_TOKEN not in record.getMessage(), (
                f"Sentinel token leaked in log at {record.name}:{record.levelname}: "
                f"{record.getMessage()}"
            )


# ---------------------------------------------------------------------------
# Test: admin prescriber API does not leak full CPF
# ---------------------------------------------------------------------------


class TestAdminPrescriberApiNoFullCpf:
    """GET /api/admin/prescriber must not expose the full CPF."""

    async def test_response_has_no_full_cpf(
        self, client: AsyncClient, db: AsyncSession
    ):
        """The admin prescriber response contains cpf_last4 but not the full CPF."""
        user = await _create_admin_user(db)

        p = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            user_id=user.id,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name="Test",
            family_name="Doctor",
            cpf_encrypted=encrypt_setting(SENTINEL_CPF),
            cpf_last4=SENTINEL_CPF[-4:],
            board_code="CRM",
            board_number="12345",
            board_state="SP",
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)

        tokens = await _login(client)
        r = await client.get(
            "/api/admin/prescriber",
            headers=_auth(tokens),
        )
        assert r.status_code == 200
        data = r.json()

        # cpf_last4 is present
        assert data.get("cpf_last4") == SENTINEL_CPF[-4:]

        # cpf_encrypted must NOT be in the response
        assert "cpf_encrypted" not in data, "Response must not contain cpf_encrypted"

        # The full CPF must not appear anywhere in the serialized response
        assert SENTINEL_CPF not in json.dumps(data), "Full CPF leaked in response"