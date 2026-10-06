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


# ---------------------------------------------------------------------------
# Redaction backstop — redact_log_message + _RedisLogHandler.emit
# ---------------------------------------------------------------------------


class TestRedactLogMessage:
    """Unit tests for redact_log_message()."""

    def test_redacts_token_in_query_param(self):
        from app.core.log_handler import redact_log_message

        msg = "Downloading PDF from https://storage.example.com/doc.pdf?token=abc123&sig=xyz"
        result = redact_log_message(msg)
        assert "abc123" not in result
        assert "token=" in result  # param name preserved
        assert "[REDACTED]" in result

    def test_redacts_api_key_in_query_param(self):
        from app.core.log_handler import redact_log_message

        msg = "Request to https://api.example.com?api-key=sk-abc123&secret-key=xyz789"
        result = redact_log_message(msg)
        assert "sk-abc123" not in result
        assert "xyz789" not in result

    def test_redacts_bearer_token(self):
        from app.core.log_handler import redact_log_message

        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redact_log_message(msg)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "Bearer" in result

    def test_redacts_cpf_formatted(self):
        from app.core.log_handler import redact_log_message

        msg = "CPF do paciente: 123.456.789-01"
        result = redact_log_message(msg)
        assert "123.456.789-01" not in result
        assert "[REDACTED-CPF]" in result

    def test_redacts_cpf_bare(self):
        from app.core.log_handler import redact_log_message

        msg = "CPF: 12345678901"
        result = redact_log_message(msg)
        assert "12345678901" not in result

    def test_preserves_diagnostic_uuids(self):
        """UUIDs must NOT be redacted."""
        from app.core.log_handler import redact_log_message

        msg = "Patient 550e8400-e29b-41d4-a716-446655440000 status=Ativo"
        result = redact_log_message(msg)
        assert "550e8400-e29b-41d4-a716-446655440000" in result
        assert "Ativo" in result

    def test_preserves_file_paths(self):
        from app.core.log_handler import redact_log_message

        msg = "Memed GET /prescricoes/presc_42/url-document/full"
        result = redact_log_message(msg)
        assert "/prescricoes/presc_42/url-document/full" in result

    def test_preserves_entity_names(self):
        from app.core.log_handler import redact_log_message

        msg = "City: São Paulo, Specialty: Pediatria"
        result = redact_log_message(msg)
        assert "São Paulo" in result
        assert "Pediatria" in result

    def test_empty_message(self):
        from app.core.log_handler import redact_log_message

        assert redact_log_message("") == ""

    def test_no_secrets_no_change(self):
        from app.core.log_handler import redact_log_message

        msg = "Processing complete for patient 42"
        assert redact_log_message(msg) == msg

    def test_redacts_signature_param(self):
        from app.core.log_handler import redact_log_message

        msg = "URL: https://storage.example.com/doc.pdf?X-Amz-Signature=abc123def456"
        result = redact_log_message(msg)
        assert "abc123def456" not in result

    def test_redacts_secret_param(self):
        from app.core.log_handler import redact_log_message

        msg = "URL: https://example.com?secret=super-secret-value"
        result = redact_log_message(msg)
        assert "super-secret-value" not in result

    def test_preserves_status_codes(self):
        from app.core.log_handler import redact_log_message

        msg = "HTTP 200 OK, response took 342ms"
        result = redact_log_message(msg)
        assert "200" in result
        assert "342ms" in result

    def test_preserves_short_ids(self):
        """Short alphanumeric IDs (usr_001, ext-1, presc_42) must NOT be redacted."""
        from app.core.log_handler import redact_log_message

        msg = "User usr_001, external_id ext-1, prescription presc_42"
        result = redact_log_message(msg)
        assert "usr_001" in result
        assert "ext-1" in result
        assert "presc_42" in result


class TestRedisLogHandlerRedaction:
    """Integration test: emit() redacts secrets before publishing to queue."""

    def test_emit_redacts_secret_in_msg(self):
        from app.core.log_handler import _RedisLogHandler
        import queue as _queue

        handler = _RedisLogHandler("redis://localhost:63799/0")
        test_queue: _queue.SimpleQueue = _queue.SimpleQueue()
        handler._queue = test_queue  # swap in test queue

        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="Downloading PDF from https://storage.example.com/doc.pdf?token=abc123-secret-token-xyz",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        payload = json.loads(test_queue.get_nowait())
        assert "abc123-secret-token-xyz" not in payload["msg"]
        assert "[REDACTED]" in payload["msg"]

    def test_emit_preserves_clean_message(self):
        from app.core.log_handler import _RedisLogHandler
        import queue as _queue

        handler = _RedisLogHandler("redis://localhost:63799/0")
        test_queue: _queue.SimpleQueue = _queue.SimpleQueue()
        handler._queue = test_queue

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Prescription presc_42 captured successfully",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        payload = json.loads(test_queue.get_nowait())
        assert payload["msg"] == "Prescription presc_42 captured successfully"

    def test_emit_redacts_exc_info(self):
        from app.core.log_handler import _RedisLogHandler
        import queue as _queue
        import sys as _sys

        handler = _RedisLogHandler("redis://localhost:63799/0")
        test_queue: _queue.SimpleQueue = _queue.SimpleQueue()
        handler._queue = test_queue

        try:
            raise ValueError("Failed to download https://storage.example.com/doc.pdf?token=abc123-secret")
        except ValueError:
            exc_info = _sys.exc_info()  # (type, value, tb) tuple
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="Something failed",
                args=(),
                exc_info=exc_info,
            )
            handler.emit(record)

        payload = json.loads(test_queue.get_nowait())
        assert "abc123-secret" not in payload.get("exc", "")
        assert "[REDACTED]" in payload.get("exc", "")

    def test_emit_preserves_metadata(self):
        """The envelope fields (ts, level, logger, source) must survive."""
        from app.core.log_handler import _RedisLogHandler
        import queue as _queue

        handler = _RedisLogHandler("redis://localhost:63799/0")
        test_queue: _queue.SimpleQueue = _queue.SimpleQueue()
        handler._queue = test_queue

        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname=__file__,
            lineno=42,
            msg="Disk space low",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        payload = json.loads(test_queue.get_nowait())
        assert payload["level"] == "WARNING"
        assert payload["logger"] == "test.logger"
        assert payload["msg"] == "Disk space low"
        assert "ts" in payload
        assert "source" in payload