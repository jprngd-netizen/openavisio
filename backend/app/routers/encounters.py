import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.encounter import Encounter
from app.models.user import User
from app.schemas.encounter import EncounterCreateRequest, EncounterDto, EncounterUpdateRequest

router = APIRouter()


@router.get("/patients/{patient_id}/encounters", response_model=list[EncounterDto])
async def list_encounters(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    q = (
        select(Encounter)
        .where(Encounter.patient_id == patient_id, Encounter.is_deleted == False)  # noqa: E712
        .order_by(Encounter.encounter_date.desc())
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/patients/{patient_id}/encounters", response_model=EncounterDto, status_code=status.HTTP_201_CREATED)
async def create_encounter(
    patient_id: uuid.UUID,
    body: EncounterCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    encounter = Encounter(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(encounter)
    await db.commit()
    await db.refresh(encounter)
    return encounter


@router.get("/encounters/{encounter_id}", response_model=EncounterDto)
async def get_encounter(
    encounter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False))  # noqa: E712
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(encounter.patient_id, user, db)
    return encounter


@router.patch("/encounters/{encounter_id}", response_model=EncounterDto)
async def update_encounter(
    encounter_id: uuid.UUID,
    body: EncounterUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False))  # noqa: E712
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(encounter, field, value)
    await db.commit()
    await db.refresh(encounter)
    return encounter


@router.delete("/encounters/{encounter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_encounter(
    encounter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False))  # noqa: E712
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)
    encounter.is_deleted = True
    await db.commit()