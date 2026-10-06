"""Tests for T2.1 — real persisted ``failed`` state outside the rollback transaction.

When ``capture_signed_pdf`` raises, the prescription must get ``status=failed``
and ``failure_reason`` in a **separate** session that survives the request
session's rollback.  The ``signature_state`` must be ``"signed"`` (set before
the capture attempt) so that retry knows not to re-sign.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.deps import get_memed_client
from app.models.prescription import Prescription, PrescriptionStatus
from app.services.prescriptions.fakes import FakeMemedClient

from tests.test_prescription_api import (
    _auth,
    _create_patient,
    _create_prescriber,
    _create_user,
    _login,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _same_connection_factory(conn):
    """Return a session factory bound to *conn* (savepoint semantics)."""
    return lambda: AsyncSession(
        bind=conn,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


# ---------------------------------------------------------------------------
# T2.1 — Failed state persistence
# ---------------------------------------------------------------------------


class TestFailedTransition:
    """When ``capture_signed_pdf`` raises, the prescription gets ``status=failed``."""

    async def _setup_rx(self, db: AsyncSession, client: AsyncClient) -> tuple[dict, uuid.UUID]:
        """Create a user, patient, prescriber, and draft prescription.

        Returns (tokens, rx_id).
        """
        user = await _create_user(db, "rx_t21@test.com", role="admin")
        tokens = await _login(client, "rx_t21@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = uuid.UUID(r.json()["id"])
        return tokens, rx_id

    async def test_capture_failure_sets_failed_state(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A capture failure sets ``status=failed`` and ``failure_reason``."""
        from app.deps import get_session_factory
        from app.main import app

        fake = FakeMemedClient()
        app.dependency_overrides[get_memed_client] = lambda: fake

        # Override session factory to use same connection (savepoint semantics)
        conn = await db.connection()
        factory = _same_connection_factory(conn)
        app.dependency_overrides[get_session_factory] = lambda: factory

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Force a capture failure by making download_pdf raise
            with patch.object(fake, "download_pdf", side_effect=ValueError("simulated-download-failure")):
                r = await client.post(
                    f"/api/prescriptions/{rx_id}/capture",
                    json={"prescription_id": "memed-fail-1", "signed": True},
                    headers=_auth(tokens),
                )
            # Should return an error (409 for ValueError, 500 for others)
            assert r.status_code in (409, 500), f"Expected error, got {r.status_code}: {r.text}"

            # Read the prescription in a new session on the same connection
            # to verify the failed state (the request session may have rolled back)
            async with factory() as check_session:
                rx = await check_session.get(Prescription, rx_id)
                assert rx is not None, "Prescription should still exist"
                assert rx.status == PrescriptionStatus.failed, (
                    f"Expected failed, got {rx.status}"
                )
                assert rx.failure_reason is not None, "failure_reason should be set"
                assert "simulated-download-failure" in rx.failure_reason
                assert rx.signature_state == "signed", (
                    f"Expected signature_state=signed, got {rx.signature_state}"
                )
        finally:
            app.dependency_overrides.pop(get_memed_client, None)
            app.dependency_overrides.pop(get_session_factory, None)

    async def test_failed_state_survives_request_rollback(
        self, client: AsyncClient, db: AsyncSession
    ):
        """The failed state persists even after the request session rolls back.

        Uses a session on the same connection (savepoint semantics) to verify
        the write is visible after ``capture_signed_pdf``'s internal rollback.
        The separate session's commit is a savepoint release within the same
        outer transaction, so its writes survive the request session's rollback
        to an earlier savepoint.
        """
        from app.deps import get_session_factory
        from app.main import app

        fake = FakeMemedClient()
        app.dependency_overrides[get_memed_client] = lambda: fake

        conn = await db.connection()
        factory = _same_connection_factory(conn)
        app.dependency_overrides[get_session_factory] = lambda: factory

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Force a capture failure
            with patch.object(fake, "download_pdf", side_effect=ValueError("simulated-failure")):
                r = await client.post(
                    f"/api/prescriptions/{rx_id}/capture",
                    json={"prescription_id": "memed-fail-2", "signed": True},
                    headers=_auth(tokens),
                )
            assert r.status_code in (409, 500)

            # Read the prescription in a new session on the same connection.
            # The failed state must be visible here because the separate
            # session's savepoint was released before the rollback.
            async with factory() as check_session:
                rx = await check_session.get(Prescription, rx_id)
                assert rx is not None
                assert rx.status == PrescriptionStatus.failed, (
                    f"Expected failed, got {rx.status} — "
                    "the failed state must survive the request session's rollback"
                )
                assert rx.failure_reason is not None
                assert rx.signature_state == "signed"
        finally:
            app.dependency_overrides.pop(get_memed_client, None)
            app.dependency_overrides.pop(get_session_factory, None)

    async def test_retry_available_after_failure(
        self, client: AsyncClient, db: AsyncSession
    ):
        """After a failed capture, retry transitions to draft.

        Sets ``signature_state`` back to ``none`` to simulate a failure that
        occurred before the BirdID signature was completed (e.g. a network
        error during PDF download).  When ``signature_state`` is ``signed``,
        retry re-archives instead — that path is tested in
        ``test_retry_no_double_sign``.
        """
        from app.deps import get_session_factory
        from app.main import app

        fake = FakeMemedClient()
        app.dependency_overrides[get_memed_client] = lambda: fake

        conn = await db.connection()
        factory = _same_connection_factory(conn)
        app.dependency_overrides[get_session_factory] = lambda: factory

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Force a capture failure
            with patch.object(fake, "download_pdf", side_effect=ValueError("simulated-failure")):
                r = await client.post(
                    f"/api/prescriptions/{rx_id}/capture",
                    json={"prescription_id": "memed-fail-3", "signed": True},
                    headers=_auth(tokens),
                )
            assert r.status_code in (409, 500)

            # Verify failed state
            async with factory() as check_session:
                rx = await check_session.get(Prescription, rx_id)
                assert rx.status == PrescriptionStatus.failed

            # Reset signature_state to none so retry goes failed → draft
            # (simulates a failure before BirdID signature completed)
            from sqlalchemy import update as sql_update
            stmt = (
                sql_update(Prescription)
                .where(Prescription.id == rx_id)
                .values(signature_state="none")
            )
            await db.execute(stmt)
            await db.commit()

            # Retry should transition failed → draft
            r = await client.post(
                f"/api/prescriptions/{rx_id}/retry",
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"Retry failed: {r.text}"
            assert r.json()["status"] == "draft"
        finally:
            app.dependency_overrides.pop(get_memed_client, None)
            app.dependency_overrides.pop(get_session_factory, None)


class TestDuplicateCaptureGuard:
    """Duplicate ``prescricaoImpressa`` events must not corrupt an issued prescription.

    T2.2 hard rule: the signing path is only reachable from
    ``signature_state=none``.  A duplicate event on an already-issued
    prescription must leave ``status=issued`` and ``signature_state=archived``
    unchanged.
    """

    async def test_duplicate_capture_on_issued_leaves_state_unchanged(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A duplicate capture event on an issued prescription is a no-op."""
        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        try:
            user = await _create_user(db, "rx_dup@test.com", role="admin")
            tokens = await _login(client, "rx_dup@test.com")
            patient = await _create_patient(db, user)
            await _create_prescriber(db, user)

            # Create draft
            r = await client.post(
                f"/api/patients/{patient.id}/prescriptions",
                headers=_auth(tokens),
            )
            assert r.status_code == 201
            rx_id = r.json()["id"]

            # First capture succeeds
            r = await client.post(
                f"/api/prescriptions/{rx_id}/capture",
                json={"prescription_id": "memed-dup-1", "signed": True},
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"First capture failed: {r.text}"
            assert r.json()["status"] == "issued"
            assert r.json()["signature_state"] == "archived"

            # Second (duplicate) capture event — must be a no-op
            r = await client.post(
                f"/api/prescriptions/{rx_id}/capture",
                json={"prescription_id": "memed-dup-2", "signed": True},
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"Duplicate capture failed: {r.text}"
            result = r.json()
            assert result["status"] == "issued", (
                f"Expected issued, got {result['status']} — "
                "duplicate capture must not change status"
            )
            assert result["signature_state"] == "archived", (
                f"Expected signature_state=archived, got {result['signature_state']} — "
                "duplicate capture must not overwrite signature_state"
            )

            # Only one PrescriptionDocument must exist
            from sqlalchemy import select
            from app.models.prescription import PrescriptionDocument

            docs = (
                await db.execute(
                    select(PrescriptionDocument).where(
                        PrescriptionDocument.prescription_id == uuid.UUID(rx_id)
                    )
                )
            ).scalars().all()
            assert len(docs) == 1, (
                f"Expected 1 PrescriptionDocument, got {len(docs)} — "
                "duplicate capture must not create a second document"
            )
        finally:
            app.dependency_overrides.pop(get_memed_client, None)