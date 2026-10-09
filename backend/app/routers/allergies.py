import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.allergy import Allergy
from app.models.user import User
from app.schemas.allergy import (
    AllergyConflictDto,
    AllergyCreateRequest,
    AllergyDto,
    AllergyUpdateRequest,
)
from app.services.allergy_alert import find_allergy_conflicts

router = APIRouter()


async def _load(db: AsyncSession, patient_id: uuid.UUID) -> list[Allergy]:
    result = await db.execute(
        select(Allergy).where(
            Allergy.patient_id == patient_id, Allergy.is_deleted == False  # noqa: E712
        )
    )
    return list(result.scalars().all())


@router.get("/patients/{patient_id}/allergies", response_model=list[AllergyDto])
async def list_allergies(
    patient_id: uuid.UUID,
    allergy_status: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = select(Allergy).where(
        Allergy.patient_id == patient_id, Allergy.is_deleted == False  # noqa: E712
    )
    if allergy_status:
        q = q.where(Allergy.clinical_status == allergy_status)
    q = q.order_by(Allergy.created_at)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/patients/{patient_id}/allergies",
    response_model=AllergyDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_allergy(
    patient_id: uuid.UUID,
    body: AllergyCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    allergy = Allergy(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(allergy)
    await db.commit()
    await db.refresh(allergy)
    return allergy


@router.get("/allergies/{allergy_id}", response_model=AllergyDto)
async def get_allergy(
    allergy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allergy = await db.get(Allergy, allergy_id)
    if not allergy or allergy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(allergy.patient_id, user, db)
    return allergy


@router.patch("/allergies/{allergy_id}", response_model=AllergyDto)
async def update_allergy(
    allergy_id: uuid.UUID,
    body: AllergyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allergy = await db.get(Allergy, allergy_id)
    if not allergy or allergy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(allergy.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(allergy, field, value)
    await db.commit()
    await db.refresh(allergy)
    return allergy


@router.delete("/allergies/{allergy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allergy(
    allergy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allergy = await db.get(Allergy, allergy_id)
    if not allergy or allergy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(allergy.patient_id, user, db, AccessLevel.contribute)
    allergy.is_deleted = True
    await db.commit()


@router.get("/patients/{patient_id}/allergy-alerts", response_model=list[AllergyConflictDto])
async def allergy_alerts(
    patient_id: uuid.UUID,
    substance: list[str] | None = Query(None, description="Prescription substance names to check"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Conflicts between the patient's active allergies and the given substances.

    Called by the prescription screen before issuing; the empty list means safe.
    """
    await require_patient_access(patient_id, user, db)
    allergies = await _load(db, patient_id)
    return find_allergy_conflicts(allergies, substance or [])
