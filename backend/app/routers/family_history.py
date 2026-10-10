import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.family_history import FamilyHistory
from app.models.user import User
from app.schemas.family_history import (
    FamilyHistoryCreateRequest,
    FamilyHistoryDto,
    FamilyHistoryUpdateRequest,
)

router = APIRouter()


@router.get("/patients/{patient_id}/family-history", response_model=list[FamilyHistoryDto])
async def list_family_history(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(FamilyHistory)
        .where(
            FamilyHistory.patient_id == patient_id,
            FamilyHistory.is_deleted == False,  # noqa: E712
        )
        .order_by(FamilyHistory.created_at)
    )
    return result.scalars().all()


@router.post(
    "/patients/{patient_id}/family-history",
    response_model=FamilyHistoryDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_family_history(
    patient_id: uuid.UUID,
    body: FamilyHistoryCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    entry = FamilyHistory(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/family-history/{entry_id}", response_model=FamilyHistoryDto)
async def get_family_history(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(FamilyHistory, entry_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db)
    return entry


@router.patch("/family-history/{entry_id}", response_model=FamilyHistoryDto)
async def update_family_history(
    entry_id: uuid.UUID,
    body: FamilyHistoryUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(FamilyHistory, entry_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/family-history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_family_history(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(FamilyHistory, entry_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(entry.patient_id, user, db, AccessLevel.contribute)
    entry.is_deleted = True
    await db.commit()
