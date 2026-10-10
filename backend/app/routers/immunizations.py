import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.immunization import Immunization
from app.models.user import User
from app.schemas.immunization import (
    ImmunizationCreateRequest,
    ImmunizationDto,
    ImmunizationUpdateRequest,
)

router = APIRouter()


@router.get("/patients/{patient_id}/immunizations", response_model=list[ImmunizationDto])
async def list_immunizations(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Immunization)
        .where(
            Immunization.patient_id == patient_id,
            Immunization.is_deleted == False,  # noqa: E712
        )
        .order_by(Immunization.occurrence_date.desc().nullslast(), Immunization.created_at)
    )
    return result.scalars().all()


@router.post(
    "/patients/{patient_id}/immunizations",
    response_model=ImmunizationDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_immunization(
    patient_id: uuid.UUID,
    body: ImmunizationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    immunization = Immunization(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(immunization)
    await db.commit()
    await db.refresh(immunization)
    return immunization


@router.get("/immunizations/{immunization_id}", response_model=ImmunizationDto)
async def get_immunization(
    immunization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    immunization = await db.get(Immunization, immunization_id)
    if not immunization or immunization.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(immunization.patient_id, user, db)
    return immunization


@router.patch("/immunizations/{immunization_id}", response_model=ImmunizationDto)
async def update_immunization(
    immunization_id: uuid.UUID,
    body: ImmunizationUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    immunization = await db.get(Immunization, immunization_id)
    if not immunization or immunization.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(immunization.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(immunization, field, value)
    await db.commit()
    await db.refresh(immunization)
    return immunization


@router.delete("/immunizations/{immunization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_immunization(
    immunization_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    immunization = await db.get(Immunization, immunization_id)
    if not immunization or immunization.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(immunization.patient_id, user, db, AccessLevel.contribute)
    immunization.is_deleted = True
    await db.commit()
