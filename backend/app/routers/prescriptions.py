"""Prescription API endpoints.

Follows the same patterns as ``routers/medications.py`` for CRUD operations
and ``routers/admin.py`` for audit logging.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.access import AccessLevel, require_patient_access
from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import decrypt_str
from app.core.patient_keys import get_patient_kek
from app.core.ratelimit import client_ip, enforce
from app.deps import get_current_user, get_memed_client, get_session_factory
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.prescription import (
    PRESCRIBER_SINGLETON_ID,
    Prescriber,
    Prescription,
    PrescriptionDocument,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.models.user import User, UserRole
from app.schemas.prescription import (
    MemedSessionResponse,
    PrescriptionDto,
    PrescriptionItemDto,
    PrescriptionUpdateRequest,
)
from app.services.prescriptions.archive import capture_signed_pdf, read_signed_pdf
from app.services.prescriptions.events import (
    CaptureMetadata,
    UnparsableMemedEvent,
    parse_prescricao_excluida,
    parse_prescricao_impressa,
)
from app.services.prescriptions.ports import MemedClient
from app.services.prescriptions.prescriber import fresh_token
from app.services.prescriptions.state import (
    InvalidTransition,
    StalePrescription,
    can_edit_items,
    check_version,
    transition,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_dto(rx: Prescription) -> PrescriptionDto:
    """Convert a Prescription ORM object to a PrescriptionDto."""
    return PrescriptionDto.model_validate(rx)


async def _get_prescriber_or_409(db: AsyncSession) -> Prescriber:
    """Get the prescriber singleton, or raise 409 if not configured."""
    p = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)
    if p is None or p.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "prescriber_not_configured"},
        )
    return p


async def _require_prescriber_user(prescriber: Prescriber, user: User) -> None:
    """Require that *user* is the linked prescriber user (default) or any admin."""
    if settings.memed_emission_policy == "any_admin":
        if user.role != UserRole.admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return
    # Default: linked_user
    if prescriber.user_id is None or prescriber.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


async def _load_rx_with_relations(
    db: AsyncSession,
    rx_id: uuid.UUID,
) -> Prescription | None:
    """Load a prescription with items and document eagerly loaded."""
    result = await db.execute(
        select(Prescription)
        .options(selectinload(Prescription.items), selectinload(Prescription.document))
        .where(Prescription.id == rx_id, Prescription.is_deleted == False)  # noqa: E712
    )
    return result.scalar_one_or_none()


def _audit_entry(
    user: User,
    entity_type: str,
    entity_id: str,
    action: str,
    changes: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Create an AuditLog entry for the current user."""
    name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    return AuditLog(
        user_id=user.id,
        user_name=name,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=changes,
        ip_address=ip_address,
        user_agent=user_agent,
    )


# ---------------------------------------------------------------------------
# List prescriptions
# ---------------------------------------------------------------------------


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PrescriptionDto])
async def list_prescriptions(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Prescription)
        .options(selectinload(Prescription.items), selectinload(Prescription.document))
        .where(
            Prescription.patient_id == patient_id,
            Prescription.is_deleted == False,  # noqa: E712
            Prescription.status != PrescriptionStatus.deleted,
        )
        .order_by(Prescription.created_at.desc())
    )
    return [_to_dto(rx) for rx in result.scalars().all()]


# ---------------------------------------------------------------------------
# Create draft
# ---------------------------------------------------------------------------


@router.post(
    "/patients/{patient_id}/prescriptions",
    response_model=PrescriptionDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    prescriber = await _get_prescriber_or_409(db)

    rx = Prescription(
        patient_id=patient_id,
        prescriber_id=prescriber.id,
        owner_id=user.id,
        status=PrescriptionStatus.draft,
        version=1,
    )
    db.add(rx)
    await db.commit()
    await db.refresh(rx)

    # Reload with relations
    rx = await _load_rx_with_relations(db, rx.id)
    return _to_dto(rx)


# ---------------------------------------------------------------------------
# Get prescription
# ---------------------------------------------------------------------------


@router.get("/prescriptions/{id}", response_model=PrescriptionDto)
async def get_prescription(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db)
    return _to_dto(rx)


# ---------------------------------------------------------------------------
# Update (autosave) — versioned compare-and-swap
# ---------------------------------------------------------------------------


@router.patch("/prescriptions/{id}", response_model=PrescriptionDto)
async def update_prescription(
    id: uuid.UUID,
    body: PrescriptionUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db, AccessLevel.contribute)

    # Reject if not draft
    if rx.status != PrescriptionStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only edit prescriptions in draft status",
        )

    # Read-side guard
    try:
        check_version(rx, body.version)
    except StalePrescription as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_version", "current_version": exc.current_version},
        )

    # Atomic compare-and-swap
    stmt = (
        update(Prescription)
        .where(Prescription.id == id, Prescription.version == body.version)
        .values(version=Prescription.version + 1)
    )
    if body.notes is not None:
        stmt = stmt.values(notes=body.notes)

    result = await db.execute(stmt)
    if result.rowcount == 0:
        # Version mismatch — reload to get current version
        await db.refresh(rx)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_version", "current_version": rx.version},
        )

    if body.notes is not None:
        rx.notes = body.notes

    # Replace items if provided
    if body.items is not None:
        # Delete existing items
        existing = await db.execute(
            select(PrescriptionItem).where(PrescriptionItem.prescription_id == id)
        )
        for item in existing.scalars().all():
            await db.delete(item)

        # Add new items
        for i, item_data in enumerate(body.items):
            db.add(
                PrescriptionItem(
                    prescription_id=id,
                    medication_name=item_data.medication_name,
                    posology=item_data.posology,
                    quantity=item_data.quantity,
                    sort_order=item_data.sort_order,
                )
            )

    await db.commit()

    await db.refresh(rx, attribute_names=["items"])
    return _to_dto(rx)


# ---------------------------------------------------------------------------
# Delete (soft, draft only)
# ---------------------------------------------------------------------------


@router.delete("/prescriptions/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prescription(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db, AccessLevel.contribute)

    if rx.status != PrescriptionStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Can only delete prescriptions in draft status",
        )

    rx.is_deleted = True
    db.add(_audit_entry(
        user, "Prescription", str(id), "deleted",
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    ))
    await db.commit()


# ---------------------------------------------------------------------------
# Memed session — fresh data-token + script URL + patient payload
# ---------------------------------------------------------------------------


@router.post("/prescriptions/{id}/memed-session")
async def memed_session(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    memed: MemedClient = Depends(get_memed_client),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db)

    prescriber = await _get_prescriber_or_409(db)
    await _require_prescriber_user(prescriber, user)

    # Rate limit: 30 session requests per 5 minutes per IP
    await enforce(f"rl:memed-session:ip:{client_ip(request)}", limit=30, window_seconds=300)

    # Fresh token from Memed
    token = await fresh_token(db, memed)
    await db.commit()  # persist token_issued_at

    # Build patient payload for setPaciente
    patient_result = await db.execute(select(Patient).where(Patient.id == rx.patient_id))
    patient = patient_result.scalar_one()

    patient_payload = {
        "idExterno": str(patient.id),
        "nome": patient.given_name,
        "sobrenome": patient.family_name,
    }
    if patient.email:
        patient_payload["email"] = patient.email
    if patient.phone:
        patient_payload["telefone"] = patient.phone
    if patient.birth_date:
        patient_payload["dataNascimento"] = patient.birth_date

    # Include CPF if available — decrypt with patient KEK
    if patient.cpf_encrypted:
        try:
            patient_kek = await get_patient_kek(db, patient.id)
            patient_payload["cpf"] = decrypt_str(patient.cpf_encrypted, patient_kek)
        except (KeyError, Exception):
            # No KEK or decryption failure — skip CPF gracefully
            pass

    data = MemedSessionResponse(
        data_token=token,
        script_url=settings.memed_script_url,
        patient=patient_payload,
    ).model_dump()
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# Capture — parse event, download PDF, archive encrypted
# ---------------------------------------------------------------------------


@router.post("/prescriptions/{id}/capture", response_model=PrescriptionDto)
async def capture_prescription(
    id: uuid.UUID,
    body: dict,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    memed: MemedClient = Depends(get_memed_client),
    session_factory=Depends(get_session_factory),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db, AccessLevel.contribute)

    prescriber = await _get_prescriber_or_409(db)
    await _require_prescriber_user(prescriber, user)

    # Rate limit: 20 capture attempts per 5 minutes per IP
    ip = client_ip(request)
    ua = request.headers.get("user-agent")
    await enforce(f"rl:capture:ip:{ip}", limit=20, window_seconds=300)

    # --- Guard: only proceed if signature_state is none/None ---
    # T2.2 hard rule: the signing path is only reachable from
    # signature_state=none.  An already-signed or already-archived
    # prescription must not be re-captured.
    sig_state = rx.signature_state or "none"
    if sig_state == "archived":
        # Already fully captured — return as-is
        return _to_dto(rx)
    if sig_state == "signed":
        # Signature confirmed but archival failed — retry endpoint handles it
        return _to_dto(rx)

    # Parse the unverified event payload
    try:
        metadata = parse_prescricao_impressa(body)
    except UnparsableMemedEvent as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unparsable_event", "keys": exc.keys},
        )

    # --- Persist signature_state=signed + memed_prescription_id in a separate ---
    # --- session BEFORE the download/archive attempt, so it survives rollback ---
    # Use UPDATE (not SELECT-then-modify) because the separate session may be
    # on a different connection where the prescription is not yet visible.
    async with session_factory() as fail_safe_session:
        stmt = (
            update(Prescription)
            .where(Prescription.id == id)
            .values(
                signature_state="signed",
                memed_prescription_id=metadata.memed_prescription_id,
            )
        )
        await fail_safe_session.execute(stmt)
        await fail_safe_session.commit()

    # Capture and archive (commits internally)
    try:
        doc = await capture_signed_pdf(db, rx, prescriber, metadata, memed)
    except Exception as exc:
        # --- Persist failed state in a separate session ---
        # The request session may have been rolled back by capture_signed_pdf,
        # so we cannot reuse it.  Open a fresh session instead.
        async with session_factory() as fail_session:
            stmt = (
                update(Prescription)
                .where(Prescription.id == id)
                .values(
                    status=PrescriptionStatus.failed,
                    failure_reason=str(exc),
                )
            )
            await fail_session.execute(stmt)
            fail_session.add(
                _audit_entry(
                    user, "Prescription", str(id), "failed",
                    {"reason": str(exc)},
                    ip_address=ip,
                    user_agent=ua,
                )
            )
            await fail_session.commit()

        # Expire the rx object so the retry endpoint reloads from DB
        # and sees the failed state written by the separate session.
        db.expire(rx)

        if isinstance(exc, ValueError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        raise

    # Set signature_state to archived on success
    rx.signature_state = "archived"

    # Audit log (separate transaction)
    db.add(_audit_entry(user, "Prescription", str(id), "updated", {"status": "issued"}, ip_address=ip, user_agent=ua))
    await db.commit()

    # Reload
    rx = await _load_rx_with_relations(db, id)
    return _to_dto(rx)


# ---------------------------------------------------------------------------
# Memed deleted — prescricaoExcluida event
# ---------------------------------------------------------------------------


@router.post("/prescriptions/{id}/memed-deleted")
async def memed_deleted(
    id: uuid.UUID,
    body: dict,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db, AccessLevel.contribute)

    prescriber = await _get_prescriber_or_409(db)
    await _require_prescriber_user(prescriber, user)

    # Parse the unverified event payload
    try:
        memed_id = parse_prescricao_excluida(body)
    except UnparsableMemedEvent as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "unparsable_event", "keys": exc.keys},
        )

    # Transition to deleted
    try:
        transition(rx, PrescriptionStatus.deleted)
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    rx.deleted_by_memed_at = datetime.now(timezone.utc)
    db.add(
        _audit_entry(
            user,
            "Prescription",
            str(id),
            "deleted",
            {"status": "deleted", "memed_prescription_id": memed_id},
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Retry — failed → draft
# ---------------------------------------------------------------------------


@router.post("/prescriptions/{id}/retry", response_model=PrescriptionDto)
async def retry_prescription(
    id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    memed: MemedClient = Depends(get_memed_client),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db, AccessLevel.contribute)

    ip = client_ip(request)
    ua = request.headers.get("user-agent")

    # Rate limit: 10 retry attempts per 5 minutes per IP
    await enforce(f"rl:retry:ip:{ip}", limit=10, window_seconds=300)

    # Determine what to do based on signature_state
    sig_state = rx.signature_state or "none"

    if sig_state == "archived":
        # Nothing to do — return as-is
        return _to_dto(rx)

    if sig_state == "signed":
        # Re-archive only — do NOT re-sign, do NOT transition to draft.
        # The prescription already has memed_prescription_id set.
        prescriber = await _get_prescriber_or_409(db)
        await _require_prescriber_user(prescriber, user)

        metadata = CaptureMetadata(
            memed_prescription_id=rx.memed_prescription_id,
            signed=True,
            file_name="prescription.pdf",
        )
        doc = await capture_signed_pdf(db, rx, prescriber, metadata, memed)

        # Set signature_state to archived
        rx.signature_state = "archived"

        db.add(
            _audit_entry(
                user, "Prescription", str(id), "updated",
                {"status": "issued", "signature_state": "archived"},
                ip_address=ip,
                user_agent=ua,
            )
        )
        await db.commit()

        rx = await _load_rx_with_relations(db, id)
        return _to_dto(rx)

    # sig_state == "none" — normal retry: failed → draft
    try:
        transition(rx, PrescriptionStatus.draft)
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await db.commit()
    rx = await _load_rx_with_relations(db, id)
    return _to_dto(rx)


# ---------------------------------------------------------------------------
# Download document — stream decrypted PDF
# ---------------------------------------------------------------------------


@router.get("/prescriptions/{id}/document")
async def get_prescription_document(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await _load_rx_with_relations(db, id)
    if not rx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(rx.patient_id, user, db)

    try:
        pdf_bytes = await read_signed_pdf(db, rx)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    doc = rx.document
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{doc.file_name}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )