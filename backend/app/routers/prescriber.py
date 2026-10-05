"""Admin prescriber API endpoints.

Manages the singleton Prescriber record and provides Memed reference-data
lookups (cities, specialties) for the admin UI.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import encrypt_setting
from app.deps import get_memed_client, require_admin
from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber
from app.models.user import User
from app.schemas.prescription import PrescriberDto, PrescriberUpdateRequest, ReferenceDataItem
from app.services.prescriptions.ports import MemedClient
from app.services.prescriptions.prescriber import (
    cached_cities,
    cached_specialties,
    ensure_prescriber,
)

router = APIRouter()


def _to_dto(p: Prescriber) -> PrescriberDto:
    """Convert a Prescriber ORM object to a PrescriberDto (no cpf_encrypted)."""
    return PrescriberDto.model_validate(p)


# ---------------------------------------------------------------------------
# GET /api/admin/prescriber
# ---------------------------------------------------------------------------


@router.get("/prescriber", response_model=PrescriberDto)
async def get_prescriber(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return the singleton prescriber, or 404 if not configured."""
    p = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)
    if p is None or p.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_dto(p)


# ---------------------------------------------------------------------------
# PUT /api/admin/prescriber — upsert
# ---------------------------------------------------------------------------


@router.put("/prescriber", response_model=PrescriberDto)
async def upsert_prescriber(
    body: PrescriberUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    memed: MemedClient = Depends(get_memed_client),
):
    """Create or update the singleton prescriber.

    CPF is encrypted at rest (``encrypt_setting``).  If ``cpf`` is omitted
    (``None``) and a prescriber already exists, the existing CPF is preserved.
    """
    existing = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)

    if existing:
        # Update existing
        existing.given_name = body.given_name
        existing.family_name = body.family_name
        if body.user_id is not None:
            existing.user_id = body.user_id
        if body.cpf is not None:
            existing.cpf_encrypted = encrypt_setting(body.cpf)
            existing.cpf_last4 = body.cpf[-4:] if len(body.cpf) >= 4 else body.cpf
        if body.birth_date is not None:
            existing.birth_date = date.fromisoformat(body.birth_date)
        if body.board_code is not None:
            existing.board_code = body.board_code
        if body.board_number is not None:
            existing.board_number = body.board_number
        if body.board_state is not None:
            existing.board_state = body.board_state
        if body.email is not None:
            existing.email = body.email
        if body.phone is not None:
            existing.phone = body.phone
        if body.sex is not None:
            existing.sex = body.sex
        if body.city_id is not None:
            existing.city_id = body.city_id
        if body.specialty_id is not None:
            existing.specialty_id = body.specialty_id
        prescriber = existing
    else:
        # Create new — CPF is required
        if not body.cpf:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="CPF is required when creating a prescriber",
            )
        cpf_encrypted = encrypt_setting(body.cpf)
        cpf_last4 = body.cpf[-4:] if body.cpf and len(body.cpf) >= 4 else None
        birth = date.fromisoformat(body.birth_date) if body.birth_date else None
        prescriber = Prescriber(
            id=PRESCRIBER_SINGLETON_ID,
            user_id=body.user_id,
            external_id=str(PRESCRIBER_SINGLETON_ID),
            given_name=body.given_name,
            family_name=body.family_name,
            cpf_encrypted=cpf_encrypted,
            cpf_last4=cpf_last4,
            birth_date=birth,
            board_code=body.board_code,
            board_number=body.board_number,
            board_state=body.board_state,
            email=body.email,
            phone=body.phone,
            sex=body.sex,
            city_id=body.city_id,
            specialty_id=body.specialty_id,
        )
        db.add(prescriber)

    await db.flush()

    # Sync with Memed (idempotent)
    try:
        await ensure_prescriber(db, memed)
    except Exception:
        # Memed sync failure is non-fatal for the local record
        pass

    await db.commit()
    await db.refresh(prescriber)
    return _to_dto(prescriber)


# ---------------------------------------------------------------------------
# GET /api/admin/memed/reference-data
# ---------------------------------------------------------------------------


@router.get("/memed/reference-data", response_model=list[ReferenceDataItem])
async def memed_reference_data(
    kind: str = Query(..., pattern="^(cities|specialties)$"),
    q: str | None = Query(None),
    admin: User = Depends(require_admin),
    memed: MemedClient = Depends(get_memed_client),
):
    """Search Memed reference data (cities or specialties)."""
    if kind == "cities":
        items = await cached_cities(memed, q=q)
    else:
        items = await cached_specialties(memed, q=q)
    return [ReferenceDataItem(id=item.id, name=item.name) for item in items]