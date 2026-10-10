import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.encounter import Encounter
from app.models.referral import Referral
from app.models.user import User
from app.schemas.referral import ReferralCreateRequest, ReferralDto, ReferralUpdateRequest

router = APIRouter()


async def _assert_encounter_belongs(db: AsyncSession, patient_id: uuid.UUID, encounter_id: uuid.UUID | None) -> None:
    """A referral may only link a consultation of the same patient."""
    if encounter_id is None:
        return
    encounter = (
        await db.execute(
            select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if encounter is None or encounter.patient_id != patient_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="encounter_id does not belong to this patient")


@router.get("/patients/{patient_id}/referrals", response_model=list[ReferralDto])
async def list_referrals(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Referral)
        .where(Referral.patient_id == patient_id, Referral.is_deleted == False)  # noqa: E712
        .order_by(Referral.date.desc().nullslast(), Referral.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/patients/{patient_id}/referrals",
    response_model=ReferralDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_referral(
    patient_id: uuid.UUID,
    body: ReferralCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    await _assert_encounter_belongs(db, patient_id, body.encounter_id)
    referral = Referral(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(referral)
    await db.commit()
    await db.refresh(referral)
    return referral


@router.get("/referrals/{referral_id}", response_model=ReferralDto)
async def get_referral(
    referral_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    referral = await db.get(Referral, referral_id)
    if not referral or referral.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(referral.patient_id, user, db)
    return referral


@router.patch("/referrals/{referral_id}", response_model=ReferralDto)
async def update_referral(
    referral_id: uuid.UUID,
    body: ReferralUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    referral = await db.get(Referral, referral_id)
    if not referral or referral.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(referral.patient_id, user, db, AccessLevel.contribute)
    data = body.model_dump(exclude_unset=True)
    if "encounter_id" in data:
        await _assert_encounter_belongs(db, referral.patient_id, data["encounter_id"])
    for field, value in data.items():
        setattr(referral, field, value)
    await db.commit()
    await db.refresh(referral)
    return referral


@router.delete("/referrals/{referral_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_referral(
    referral_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    referral = await db.get(Referral, referral_id)
    if not referral or referral.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(referral.patient_id, user, db, AccessLevel.contribute)
    referral.is_deleted = True
    await db.commit()
