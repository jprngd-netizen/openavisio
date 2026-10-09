import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.core.datetimes import SAO_PAULO
from app.deps import get_current_user
from app.models.medication import MedicationStatement
from app.models.user import User
from app.schemas.medication import (
    ActiveMedicationDto,
    MedicationCreateRequest,
    MedicationDto,
    MedicationUpdateRequest,
)
from app.services.medication_reconciliation import active_medications, duplicate_ids

router = APIRouter()


def med_is_active(med: MedicationStatement) -> bool:
    """Currently active = not manually stopped/completed and not past its end (#68)."""
    if med.status in ("stopped", "completed"):
        return False
    if med.effective_end is None:
        return True
    return med.effective_end.astimezone(SAO_PAULO).date() >= datetime.now(SAO_PAULO).date()


def _today_start() -> datetime:
    """Midnight today in America/Sao_Paulo — the day a course is stopped on."""
    return datetime.now(SAO_PAULO).replace(hour=0, minute=0, second=0, microsecond=0)


def _to_dto(med: MedicationStatement) -> MedicationDto:
    dto = MedicationDto.model_validate(med)
    dto.is_active = med_is_active(med)
    return dto


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationDto])
async def list_medications(
    patient_id: uuid.UUID,
    med_status: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(MedicationStatement).where(MedicationStatement.patient_id == patient_id, MedicationStatement.is_deleted == False)  # noqa: E712
    if med_status:
        q = q.where(MedicationStatement.status == med_status)
    result = await db.execute(q)
    return [_to_dto(m) for m in result.scalars().all()]


@router.get("/patients/{patient_id}/medications/active", response_model=list[ActiveMedicationDto])
async def list_active_medications(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Active medications right now, each flagged with its duplicates (WS-2).

    "Active" = status active AND currently in force (see
    ``medication_reconciliation``). ``duplicate_of`` lists the other active
    medications sharing the same substance — the encounter shows this as a
    reconciliation warning. Read-only: the CRUD routes are untouched.
    """
    await require_patient_access(patient_id, user, db)
    q = select(MedicationStatement).where(
        MedicationStatement.patient_id == patient_id,
        MedicationStatement.is_deleted == False,  # noqa: E712
    ).order_by(MedicationStatement.created_at)
    result = await db.execute(q)
    now = datetime.now(SAO_PAULO)
    active = active_medications(result.scalars().all(), now)
    dup_index = duplicate_ids(active)
    return [
        ActiveMedicationDto.model_validate(med).model_copy(
            update={"is_active": True, "duplicate_of": dup_index.get(med.id, [])}
        )
        for med in active
    ]


@router.post("/patients/{patient_id}/medications", response_model=MedicationDto, status_code=status.HTTP_201_CREATED)
async def create_medication(
    patient_id: uuid.UUID,
    body: MedicationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    med = MedicationStatement(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return _to_dto(med)


@router.get("/medications/{medication_id}", response_model=MedicationDto)
async def get_medication(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db)
    return _to_dto(med)


@router.put("/medications/{medication_id}", response_model=MedicationDto)
async def update_medication(
    medication_id: uuid.UUID,
    body: MedicationUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db, AccessLevel.contribute)
    # exclude_unset, not exclude_none: a client must be able to CLEAR a date by
    # sending null. With exclude_none an explicit null was silently dropped, so a
    # wrong extracted date could never be removed (#128).
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(med, field, value)
    # Last resort only. The UI asks for the date (#128) — this catches API clients
    # that stop a medication without saying when.
    if med.status in ("stopped", "completed") and not med.effective_end:
        med.effective_end = _today_start()
    await db.commit()
    await db.refresh(med)
    return _to_dto(med)


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    medication_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(MedicationStatement).where(MedicationStatement.id == medication_id, MedicationStatement.is_deleted == False))  # noqa: E712
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(med.patient_id, user, db, AccessLevel.contribute)
    med.is_deleted = True
    await db.commit()
