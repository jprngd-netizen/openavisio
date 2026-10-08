"""Signed PDF capture and encrypted archival service.

Downloads the signed PDF from Memed, encrypts it with the patient's KEK,
stores it as a ``PrescriptionDocument``, and transitions the prescription
to ``issued``.  Cleans up the blob on any failure after writing it — no
orphaned files.

Domain terms (see CONTEXT.md):
- PrescriptionDocument: the archived signed PDF of an issued Prescription
- Prescription: a draft or issued medical prescription for a Patient
- Prescriber: the licensed healthcare professional authorized to issue prescriptions
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_document, encrypt_document
from app.core.patient_keys import ensure_patient_kek, get_patient_kek
from app.core.storage import get_storage
from app.models.prescription import Prescription, PrescriptionDocument
from app.services.prescriptions.events import CaptureMetadata
from app.services.prescriptions.ports import MemedClient
from app.services.prescriptions.prescriber import fresh_token
from app.services.prescriptions.state import set_memed_id, transition

logger = logging.getLogger(__name__)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


def _is_sha256_hex(s: str) -> bool:
    """Return ``True`` if *s* looks like a SHA-256 hex digest (64 hex chars)."""
    return bool(_SHA256_RE.match(s))


async def capture_signed_pdf(
    db: AsyncSession,
    prescription: Prescription,
    prescriber: object,  # Prescriber — used by fresh_token
    metadata: CaptureMetadata,
    client: MemedClient,
) -> PrescriptionDocument:
    """Download, encrypt, and archive the signed PDF for *prescription*.

    Steps
        1. Reject if a ``PrescriptionDocument`` already exists for this
           prescription (second-capture guard).
        2. Get a fresh Memed token via ``fresh_token``.
        3. Get the PDF download URL from Memed.
        4. Download and validate the PDF bytes (must start with ``%PDF``).
        5. Compute the SHA-256 hash of the downloaded bytes.  If
           ``metadata.file_hash`` is present **and** looks like a SHA-256 hex
           digest (64 hex chars), compare and raise on divergence.  If it is
           present but in another format, log a warning and proceed — the
           archived hash is always the computed one.
        6. Ensure the patient's KEK exists (create on first use).
        7. Encrypt the PDF under a fresh DEK wrapped by the patient KEK.
        8. Create and flush a ``PrescriptionDocument`` to obtain its id.
        9. Write the encrypted blob to storage at ``{patient_id}/{doc_id}.enc``.
        10. Try to fetch the digital link (best-effort, non-fatal).
        11. Set ``memed_prescription_id`` on the prescription (write-once).
        12. Link the document and transition to ``issued``.
        13. Commit.

    On **any** exception after writing the blob, the blob is deleted and the
    DB transaction is rolled back — no orphaned blobs.

    Raises
        ValueError: if a ``PrescriptionDocument`` already exists for this
            prescription, or if the ``file_hash`` from the event diverges
            from the computed SHA-256.
    """
    # --- 1. Reject second capture ---
    existing = await db.execute(
        select(PrescriptionDocument).where(
            PrescriptionDocument.prescription_id == prescription.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(
            f"Prescription {prescription.id} already has a captured document"
        )

    # --- 2. Fresh token ---
    token = await fresh_token(db, client)

    # --- 3. PDF URL ---
    url = await client.get_prescription_pdf_url(
        token, metadata.memed_prescription_id
    )

    # --- 4. Download and validate ---
    data = await client.download_pdf(url)
    if not data.startswith(b"%PDF"):
        raise ValueError(
            "Downloaded content is not a valid PDF (missing %PDF magic bytes)"
        )

    # --- 5. Hash ---
    file_hash = hashlib.sha256(data).hexdigest()
    if metadata.file_hash is not None:
        if _is_sha256_hex(metadata.file_hash):
            if metadata.file_hash.lower() != file_hash:
                raise ValueError(
                    f"File hash mismatch: event reported {metadata.file_hash}, "
                    f"computed {file_hash}"
                )
        else:
            logger.warning(
                "file_hash from event is not a SHA-256 hex digest (%r) — "
                "proceeding with computed hash",
                metadata.file_hash,
            )

    # --- 6. Patient KEK ---
    patient_id = prescription.patient_id
    kek = await ensure_patient_kek(db, patient_id)

    # --- 7. Encrypt ---
    ciphertext, wrapped_dek = encrypt_document(data, kek)

    # --- 8. Create PrescriptionDocument (flush to obtain id) ---
    doc_id = uuid.uuid4()
    storage_key = f"{patient_id}/{doc_id}.enc"
    now = datetime.now(timezone.utc)

    doc = PrescriptionDocument(
        id=doc_id,
        prescription_id=prescription.id,
        file_name=metadata.file_name or "prescription.pdf",
        content_type="application/pdf",
        size=len(data),
        storage_path=storage_key,
        hash=file_hash,
        encrypted_dek=wrapped_dek,
        kek_version=1,
        signed=metadata.signed,
        memed_prescription_id=metadata.memed_prescription_id,
        captured_at=now,
    )
    db.add(doc)
    await db.flush()

    # --- 9. Write blob ---
    storage = get_storage()
    blob_written = False
    try:
        storage.write(storage_key, ciphertext)
        blob_written = True
    except Exception:
        await db.rollback()
        raise

    # --- 10. Digital link (best-effort) ---
    try:
        link_result = await client.get_digital_link(
            token, metadata.memed_prescription_id
        )
        doc.digital_link = link_result.link
        doc.unlock_code = link_result.unlock_code
    except Exception:
        logger.warning(
            "Failed to fetch digital link for prescription %s",
            metadata.memed_prescription_id,
            exc_info=True,
        )

    # --- 11. Set Memed ID (write-once) ---
    set_memed_id(prescription, metadata.memed_prescription_id)

    # --- 12. Link document and transition ---
    prescription.document = doc
    try:
        transition(prescription, "issued")
    except Exception:
        # Transition failed — remove the blob and roll back
        if blob_written:
            storage.delete(storage_key)
        await db.rollback()
        raise

    # --- 13. Commit ---
    await db.commit()
    return doc


async def attach_prescription_pdf(
    db: AsyncSession,
    prescription: Prescription,
    data: bytes,
    file_name: str,
) -> PrescriptionDocument:
    """Encrypt and archive an externally-produced prescription PDF.

    Mirrors the encryption/storage steps of :func:`capture_signed_pdf` but for
    a PDF the prescriber produced **outside** OpenAvisio — e.g. downloaded from
    Memed's own web application when the partner/API integration is not
    available (it requires a CNPJ the physician does not have).

    The archived ``PrescriptionDocument`` is marked ``signed=False`` and all
    ``memed_*`` provenance fields are left ``None``; the only archived hash is
    the SHA-256 of the uploaded bytes.

    Steps
        1. Reject if a ``PrescriptionDocument`` already exists for this
           prescription (single-document guard).
        2. Ensure the patient's KEK exists (create on first use).
        3. Encrypt the PDF under a fresh DEK wrapped by the patient KEK.
        4. Create a ``PrescriptionDocument`` and flush to obtain its id.
        5. Write the encrypted blob to storage at ``{patient_id}/{doc_id}.enc``.
        6. Link the document to the prescription and commit.

    On **any** exception after writing the blob, the blob is deleted and the
    DB transaction is rolled back — no orphaned blobs.

    Raises
        ValueError: if a ``PrescriptionDocument`` already exists for this
            prescription.
    """
    # --- 1. Reject second capture ---
    existing = await db.execute(
        select(PrescriptionDocument).where(
            PrescriptionDocument.prescription_id == prescription.id
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(
            f"Prescription {prescription.id} already has a captured document"
        )

    # --- 2. Patient KEK ---
    patient_id = prescription.patient_id
    kek = await ensure_patient_kek(db, patient_id)

    # --- 3. Encrypt ---
    ciphertext, wrapped_dek = encrypt_document(data, kek)

    # --- 4. Create PrescriptionDocument (flush to obtain id) ---
    doc_id = uuid.uuid4()
    storage_key = f"{patient_id}/{doc_id}.enc"
    now = datetime.now(timezone.utc)

    doc = PrescriptionDocument(
        id=doc_id,
        prescription_id=prescription.id,
        file_name=file_name or "prescription.pdf",
        content_type="application/pdf",
        size=len(data),
        storage_path=storage_key,
        hash=hashlib.sha256(data).hexdigest(),
        encrypted_dek=wrapped_dek,
        kek_version=1,
        signed=False,
        memed_prescription_id=None,
        captured_at=now,
    )
    db.add(doc)
    await db.flush()

    # --- 5. Write blob ---
    storage = get_storage()
    try:
        storage.write(storage_key, ciphertext)
    except Exception:
        await db.rollback()
        raise

    # --- 6. Link document and commit ---
    prescription.document = doc
    try:
        await db.commit()
    except Exception:
        storage.delete(storage_key)
        await db.rollback()
        raise
    return doc


async def read_signed_pdf(
    db: AsyncSession,
    prescription: Prescription,
) -> bytes:
    """Read and decrypt the signed PDF for *prescription*.

    Returns the decrypted PDF bytes.

    Raises
        LookupError: if the prescription has no captured document.
    """
    doc = prescription.document
    if doc is None:
        result = await db.execute(
            select(PrescriptionDocument).where(
                PrescriptionDocument.prescription_id == prescription.id
            )
        )
        doc = result.scalar_one_or_none()
    if doc is None:
        raise LookupError("Prescription has no captured document")

    ciphertext = get_storage().read(doc.storage_path)
    kek = await get_patient_kek(db, prescription.patient_id)
    return decrypt_document(ciphertext, doc.encrypted_dek, kek)