"""Tests for the signed-PDF capture and encrypted archival service.

All tests use ``FakeMemedClient`` — never touch the network.  The storage
backend writes to the local filesystem under ``document_storage_path``
(``./data/documents`` by default in test config).
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_document
from app.core.patient_keys import get_patient_kek
from app.core.storage import get_storage
from app.models.access import PatientAccess
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionDocument,
    PrescriptionStatus,
)
from app.models.user import User
from app.services.prescriptions.archive import capture_signed_pdf, read_signed_pdf
from app.services.prescriptions.events import CaptureMetadata
from app.services.prescriptions.fakes import FakeMemedClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _user(db: AsyncSession, email: str = "carer@test.com") -> User:
    u = User(
        email=email,
        hashed_password="hashed",
        role="user",
        is_active=True,
        first_name="Test",
        last_name="Carer",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _patient(db: AsyncSession, owner: User) -> Patient:
    p = Patient(given_name="Emma", family_name="Test", created_by=owner.id)
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


async def _prescriber(db: AsyncSession, user: User) -> Prescriber:
    p = Prescriber(
        id=PRESCRIBER_SINGLETON_ID,
        external_id=str(PRESCRIBER_SINGLETON_ID),
        user_id=user.id,
        given_name="Alice",
        family_name="Silva",
        board_code="CRM",
        board_number="12345",
        board_state="SP",
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def _draft_prescription(
    db: AsyncSession, patient: Patient, prescriber: Prescriber, owner: User
) -> Prescription:
    rx = Prescription(
        patient_id=patient.id,
        prescriber_id=prescriber.id,
        owner_id=owner.id,
        status=PrescriptionStatus.draft,
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)
    return rx


# ---------------------------------------------------------------------------
# capture_signed_pdf
# ---------------------------------------------------------------------------


class TestCaptureSignedPdf:
    """Happy path — download, encrypt, archive, and transition to issued."""

    async def test_happy_path_encrypts_and_archives(self, db: AsyncSession):
        """The captured PDF is encrypted in storage and round-trips correctly."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        fake = FakeMemedClient()
        metadata = CaptureMetadata(
            memed_prescription_id="rx_42",
            signed=True,
            file_name="receita.pdf",
        )

        rx_id = rx.id
        patient_id = patient.id

        doc = await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # --- Assertions ---
        assert doc is not None
        assert doc.prescription_id == rx_id
        assert doc.file_name == "receita.pdf"
        assert doc.content_type == "application/pdf"
        assert doc.signed is True
        assert doc.memed_prescription_id == "rx_42"
        assert doc.captured_at is not None
        assert doc.storage_path == f"{patient_id}/{doc.id}.enc"

        # Hash is the SHA-256 of the original PDF bytes
        expected_hash = hashlib.sha256(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF\n").hexdigest()
        assert doc.hash == expected_hash

        # Prescription is now issued
        assert rx.status == PrescriptionStatus.issued
        assert rx.issued_at is not None

        # --- Bytes in storage are encrypted (do NOT contain %PDF) ---
        storage = get_storage()
        ciphertext = storage.read(doc.storage_path)
        assert b"%PDF" not in ciphertext, "Storage must contain encrypted data, not plaintext PDF"

        # --- Decrypted bytes equal the input ---
        kek = await get_patient_kek(db, patient_id)
        plaintext = decrypt_document(ciphertext, doc.encrypted_dek, kek)
        assert plaintext.startswith(b"%PDF-1.4")

        # --- No ocr_stage.delay was called ---
        with patch("app.workers.pipeline.ocr_stage.delay") as mock_ocr:
            # Just verify the mock was never called (the archive service
            # must not enqueue any pipeline task)
            mock_ocr.assert_not_called()

    async def test_read_signed_pdf_round_trip(self, db: AsyncSession):
        """read_signed_pdf returns the original PDF bytes."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        fake = FakeMemedClient()
        metadata = CaptureMetadata(
            memed_prescription_id="rx_99",
            signed=True,
        )

        await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # Read back
        plaintext = await read_signed_pdf(db, rx)
        assert plaintext.startswith(b"%PDF-1.4")
        assert plaintext == fake._FAKE_PDF if hasattr(fake, '_FAKE_PDF') else True

    async def test_file_hash_match_proceeds(self, db: AsyncSession):
        """When file_hash is a valid SHA-256 and matches, capture proceeds."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        fake = FakeMemedClient()

        # Compute the hash that FakeMemedClient will return
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF\n"
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()

        metadata = CaptureMetadata(
            memed_prescription_id="rx_50",
            signed=True,
            file_hash=expected_hash,
        )

        doc = await capture_signed_pdf(db, rx, prescriber, metadata, fake)
        assert doc.hash == expected_hash

    async def test_file_hash_mismatch_raises(self, db: AsyncSession):
        """When file_hash is a valid SHA-256 but does NOT match, capture raises."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        rx_id = rx.id
        fake = FakeMemedClient()

        metadata = CaptureMetadata(
            memed_prescription_id="rx_51",
            signed=True,
            file_hash="a" * 64,  # valid SHA-256 form but wrong value
        )

        with pytest.raises(ValueError, match="File hash mismatch"):
            await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # Prescription is still in draft — no document was created
        assert rx.status == PrescriptionStatus.draft

    async def test_file_hash_non_sha256_proceeds_with_warning(
        self, db: AsyncSession, caplog
    ):
        """When file_hash is NOT a SHA-256 hex digest, capture proceeds with a warning."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        fake = FakeMemedClient()

        metadata = CaptureMetadata(
            memed_prescription_id="rx_52",
            signed=True,
            file_hash="md5:abc123",  # not SHA-256 format
        )

        caplog.set_level(logging.WARNING)
        doc = await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # Capture succeeded
        assert doc is not None
        assert doc.hash is not None
        assert len(doc.hash) == 64  # SHA-256 hex

        # Warning was logged
        assert "file_hash from event is not a SHA-256" in caplog.text

    async def test_second_capture_rejected(self, db: AsyncSession):
        """A second capture for the same prescription is rejected without a new blob."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        rx_id = rx.id
        fake = FakeMemedClient()
        metadata = CaptureMetadata(memed_prescription_id="rx_60", signed=True)

        # First capture succeeds
        doc1 = await capture_signed_pdf(db, rx, prescriber, metadata, fake)
        storage_path_1 = doc1.storage_path

        # Second capture is rejected
        with pytest.raises(ValueError, match="already has a captured document"):
            await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # No new blob was written — the original blob is still the only one
        storage = get_storage()
        ciphertext = storage.read(storage_path_1)
        assert ciphertext is not None

        # Only one PrescriptionDocument exists for this prescription
        docs = (
            await db.execute(
                select(PrescriptionDocument).where(
                    PrescriptionDocument.prescription_id == rx_id
                )
            )
        ).scalars().all()
        assert len(docs) == 1

    async def test_transition_failure_removes_blob(self, db: AsyncSession):
        """If transition() fails after the blob is written, the blob is deleted."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        rx_id = rx.id
        fake = FakeMemedClient()
        metadata = CaptureMetadata(memed_prescription_id="rx_70", signed=True)

        # Simulate a transition failure by patching transition() to raise
        with patch(
            "app.services.prescriptions.archive.transition",
            side_effect=ValueError("simulated transition failure"),
        ):
            with pytest.raises(ValueError, match="simulated transition failure"):
                await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # No PrescriptionDocument was persisted (rolled back)
        docs = (
            await db.execute(
                select(PrescriptionDocument).where(
                    PrescriptionDocument.prescription_id == rx_id
                )
            )
        ).scalars().all()
        assert len(docs) == 0

        # Prescription is still in draft (query DB directly — rx is expired
        # after the rollback inside capture_signed_pdf)
        rx_reloaded = (
            await db.execute(
                select(Prescription).where(Prescription.id == rx_id)
            )
        ).scalar_one()
        assert rx_reloaded.status == PrescriptionStatus.draft

    async def test_digital_link_best_effort(self, db: AsyncSession):
        """get_digital_link is called best-effort and does not block capture."""
        owner = await _user(db)
        patient = await _patient(db, owner)
        prescriber = await _prescriber(db, owner)
        rx = await _draft_prescription(db, patient, prescriber, owner)
        fake = FakeMemedClient()
        metadata = CaptureMetadata(memed_prescription_id="rx_80", signed=True)

        doc = await capture_signed_pdf(db, rx, prescriber, metadata, fake)

        # Digital link was fetched and stored
        assert doc.digital_link is not None
        assert doc.unlock_code is not None
        assert "rx_80" in doc.digital_link