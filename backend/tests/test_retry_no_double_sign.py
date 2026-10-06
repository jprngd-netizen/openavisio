"""Tests for T2.2 — idempotent retry: never re-sign an already-signed prescription.

The retry endpoint must respect ``signature_state``:

- ``none`` (or ``None``) → normal retry: transition ``failed → draft``.
- ``signed`` → **forbidden to re-sign**; re-archive the existing PDF
  (download + encrypt + store + transition to ``issued``).
- ``archived`` → nothing to do; return the prescription as-is.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

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
# T2.2 — Idempotent retry
# ---------------------------------------------------------------------------


class TestRetryNoDoubleSign:
    """Retry respects ``signature_state`` and never re-signs."""

    async def _setup_rx(self, db: AsyncSession, client: AsyncClient) -> tuple[dict, uuid.UUID]:
        """Create a user, patient, prescriber, and draft prescription.

        Returns (tokens, rx_id).
        """
        user = await _create_user(db, "rx_t22@test.com", role="admin")
        tokens = await _login(client, "rx_t22@test.com")
        patient = await _create_patient(db, user)
        await _create_prescriber(db, user)

        r = await client.post(
            f"/api/patients/{patient.id}/prescriptions",
            headers=_auth(tokens),
        )
        assert r.status_code == 201
        rx_id = uuid.UUID(r.json()["id"])
        return tokens, rx_id

    async def _set_state(
        self,
        db: AsyncSession,
        rx_id: uuid.UUID,
        status: str,
        signature_state: str,
        memed_prescription_id: str | None = None,
    ) -> None:
        """Manually set prescription state for testing."""
        values = {
            "status": status,
            "signature_state": signature_state,
        }
        if memed_prescription_id is not None:
            values["memed_prescription_id"] = memed_prescription_id
        stmt = (
            sql_update(Prescription)
            .where(Prescription.id == rx_id)
            .values(**values)
        )
        await db.execute(stmt)
        await db.commit()

    async def test_retry_signed_rearchives(
        self, client: AsyncClient, db: AsyncSession
    ):
        """When ``signature_state=signed``, retry re-archives without re-signing.

        The prescription transitions to ``issued`` and ``signature_state``
        becomes ``archived``.  The ``FakeMemedClient`` records show that
        ``get_prescription_pdf_url`` was called (re-download) but the signing
        path (``get_prescriber`` for a fresh token) is also called because
        ``capture_signed_pdf`` needs a fresh token.
        """
        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Set state to simulate "signed, archival failed"
            await self._set_state(
                db, rx_id,
                status="failed",
                signature_state="signed",
                memed_prescription_id="memed-retry-1",
            )

            # Clear the fake's call log (setup calls are irrelevant)
            fake.calls.clear()

            # Retry — should re-archive, not re-sign
            r = await client.post(
                f"/api/prescriptions/{rx_id}/retry",
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"Retry failed: {r.text}"
            result = r.json()
            assert result["status"] == "issued", (
                f"Expected issued, got {result['status']}"
            )
            assert result.get("document") is not None, (
                "Should have a PrescriptionDocument after re-archive"
            )

            # Verify signature_state is now archived
            assert result.get("signature_state") == "archived", (
                f"Expected signature_state=archived, got {result.get('signature_state')}"
            )

            # Verify the re-archive path was taken:
            # get_prescription_pdf_url must have been called (re-download)
            pdf_url_calls = [
                c for c in fake.calls
                if c[0] == "get_prescription_pdf_url"
            ]
            assert len(pdf_url_calls) >= 1, (
                "get_prescription_pdf_url should have been called for re-archive"
            )

            # download_pdf must have been called
            download_calls = [
                c for c in fake.calls
                if c[0] == "download_pdf"
            ]
            assert len(download_calls) >= 1, (
                "download_pdf should have been called for re-archive"
            )

        finally:
            app.dependency_overrides.pop(get_memed_client, None)

    async def test_retry_none_transitions_to_draft(
        self, client: AsyncClient, db: AsyncSession
    ):
        """When ``signature_state=none``, retry transitions ``failed → draft``."""
        tokens, rx_id = await self._setup_rx(db, client)

        # Set state to failed with signature_state=none
        await self._set_state(
            db, rx_id,
            status="failed",
            signature_state="none",
        )

        # Retry — should transition to draft
        r = await client.post(
            f"/api/prescriptions/{rx_id}/retry",
            headers=_auth(tokens),
        )
        assert r.status_code == 200, f"Retry failed: {r.text}"
        assert r.json()["status"] == "draft"

    async def test_retry_archived_returns_as_is(
        self, client: AsyncClient, db: AsyncSession
    ):
        """When ``signature_state=archived``, retry returns the prescription as-is."""
        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Set state to issued with signature_state=archived
            await self._set_state(
                db, rx_id,
                status="issued",
                signature_state="archived",
                memed_prescription_id="memed-retry-2",
            )

            # Clear the fake's call log
            fake.calls.clear()

            # Retry — should return as-is, no new calls
            r = await client.post(
                f"/api/prescriptions/{rx_id}/retry",
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"Retry failed: {r.text}"
            assert r.json()["status"] == "issued"

            # No new calls to the Memed client
            assert len(fake.calls) == 0, (
                f"Expected no MemedClient calls for archived retry, got {fake.calls}"
            )
        finally:
            app.dependency_overrides.pop(get_memed_client, None)

    async def test_retry_signed_rejects_draft_transition(
        self, client: AsyncClient, db: AsyncSession
    ):
        """When ``signature_state=signed``, retry must NOT transition to draft.

        The prescription must go directly to ``issued`` via re-archive, not
        through ``draft``.
        """
        fake = FakeMemedClient()
        app = client._transport.app
        app.dependency_overrides[get_memed_client] = lambda: fake

        try:
            tokens, rx_id = await self._setup_rx(db, client)

            # Set state to simulate "signed, archival failed"
            await self._set_state(
                db, rx_id,
                status="failed",
                signature_state="signed",
                memed_prescription_id="memed-retry-3",
            )

            # Retry — must go to issued, NOT draft
            r = await client.post(
                f"/api/prescriptions/{rx_id}/retry",
                headers=_auth(tokens),
            )
            assert r.status_code == 200, f"Retry failed: {r.text}"
            result = r.json()
            assert result["status"] == "issued", (
                f"Expected issued (re-archive), got {result['status']} — "
                "signed retry must NOT transition to draft"
            )
        finally:
            app.dependency_overrides.pop(get_memed_client, None)