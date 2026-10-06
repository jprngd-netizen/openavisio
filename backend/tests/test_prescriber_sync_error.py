"""Tests for prescriber sync error handling and token expiry (T1.2, T2.4).

T1.2 — Memed sync failures must be persisted as sync_status/sync_error
on the Prescriber record, rather than being silently swallowed.

T2.4 — BirdID token expiry must be distinguishable from signature failure
by recording token_issued_at locally and checking against expected validity.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.services.prescriptions.fakes import FakeMemedClient
from app.services.prescriptions.prescriber import (
    ensure_prescriber,
    fresh_token,
    is_token_expired,
)


async def _create_prescriber_in_db(
    db: AsyncSession,
    external_id: str = "ext-1",
    given_name: str = "Alice",
    family_name: str = "Silva",
) -> Prescriber:
    """Create a Prescriber record in the test database."""
    prescriber = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        external_id=external_id,
        given_name=given_name,
        family_name=family_name,
        board_code="CRM",
        board_number="12345",
        board_state="SP",
    )
    db.add(prescriber)
    await db.flush()
    return prescriber


# =========================================================================
# T1.2 — Sync error persisted
# =========================================================================


class TestPrescriberSyncError:
    """Sync failures must be persisted, not silently swallowed."""

    async def test_sync_error_persisted_on_failure(self, db: AsyncSession):
        """When MemedClient raises, sync_status=error and sync_error are set."""
        prescriber = await _create_prescriber_in_db(db)

        class _RaisingFake(FakeMemedClient):
            async def get_prescriber(self, external_id: str):
                raise RuntimeError("Connection refused by Memed")

        fake = _RaisingFake()

        # This should NOT raise — the error is caught and persisted
        result = await ensure_prescriber(db, fake)

        assert result is prescriber
        assert prescriber.sync_status == "error"
        assert prescriber.sync_error is not None
        assert "Connection refused" in prescriber.sync_error

    async def test_sync_ok_on_success(self, db: AsyncSession):
        """When MemedClient succeeds, sync_status=ok and sync_error is None."""
        prescriber = await _create_prescriber_in_db(db)
        fake = FakeMemedClient()

        result = await ensure_prescriber(db, fake)

        assert result is prescriber
        assert prescriber.sync_status == "ok"
        assert prescriber.sync_error is None

    async def test_sync_error_does_not_block_create(self, db: AsyncSession):
        """A new prescriber is still created locally even if Memed sync fails."""
        prescriber = await _create_prescriber_in_db(db)

        class _RaisingFake(FakeMemedClient):
            async def get_prescriber(self, external_id: str):
                raise RuntimeError("Memed unreachable")

        fake = _RaisingFake()

        result = await ensure_prescriber(db, fake)

        # Local record is still valid
        assert result is prescriber
        assert result.given_name == "Alice"
        # Sync error is recorded
        assert prescriber.sync_status == "error"
        assert "Memed unreachable" in prescriber.sync_error


# =========================================================================
# T2.4 — Token expiry
# =========================================================================


class TestTokenExpiry:
    """BirdID token expiry must be distinguishable from signature failure."""

    def test_token_expired_when_issued_at_is_none(self):
        """When token_issued_at is None, the token is considered expired."""
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=None,
        )
        assert is_token_expired(prescriber) is True

    def test_token_expired_when_past_validity(self):
        """Token issued more than 12h ago is expired."""
        past = datetime.now(timezone.utc) - timedelta(hours=13)
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=past,
        )
        assert is_token_expired(prescriber) is True

    def test_token_not_expired_when_within_validity(self):
        """Token issued less than 12h ago is NOT expired."""
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=recent,
        )
        assert is_token_expired(prescriber) is False

    def test_token_expired_at_boundary(self):
        """Token issued exactly 12h ago is expired (boundary)."""
        boundary = datetime.now(timezone.utc) - timedelta(hours=12)
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=boundary,
        )
        # At exactly 12h, the token is expired (not < validity)
        assert is_token_expired(prescriber) is True

    def test_token_not_expired_with_custom_validity(self):
        """Custom validity_hours parameter is respected."""
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=recent,
        )
        # 2h is within 6h validity
        assert is_token_expired(prescriber, validity_hours=6) is False
        # 2h is beyond 1h validity
        assert is_token_expired(prescriber, validity_hours=1) is True

    def test_token_expiry_with_clock_control(self):
        """Clock control: inject a specific 'now' to test edge cases."""
        issued_at = datetime(2026, 10, 6, 8, 0, 0, tzinfo=timezone.utc)
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            external_id="ext-1",
            given_name="Alice",
            family_name="Silva",
            token_issued_at=issued_at,
        )

        # At 19:59 UTC (11h59m later) — still valid
        now_11h59m = datetime(2026, 10, 6, 19, 59, 0, tzinfo=timezone.utc)
        assert is_token_expired(prescriber, now=now_11h59m) is False

        # At 20:01 UTC (12h01m later) — expired
        now_12h01m = datetime(2026, 10, 6, 20, 1, 0, tzinfo=timezone.utc)
        assert is_token_expired(prescriber, now=now_12h01m) is True

    async def test_fresh_token_records_token_issued_at(self, db: AsyncSession):
        """fresh_token records token_issued_at on the prescriber."""
        prescriber = await _create_prescriber_in_db(db)
        assert prescriber.token_issued_at is None  # not set yet

        fake = FakeMemedClient()
        token = await fresh_token(db, fake)

        assert token == "fake-token-001"
        # token_issued_at was set by fresh_token
        assert prescriber.token_issued_at is not None
        # It should be recent (within the last 10 seconds)
        now = datetime.now(timezone.utc)
        diff = now - prescriber.token_issued_at
        assert diff.total_seconds() < 10