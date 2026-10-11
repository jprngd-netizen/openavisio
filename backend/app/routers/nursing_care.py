import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.nursing_care import NursingCare, NursingCareCategory
from app.models.pregnancy import Pregnancy
from app.models.user import User
from app.schemas.nursing_care import (
    NursingCareCreateRequest,
    NursingCareDto,
    NursingCareUpdateRequest,
)

router = APIRouter()


async def _validate_gestation(
    db: AsyncSession, patient_id: uuid.UUID, category: str, pregnancy_id: uuid.UUID | None
) -> None:
    """Enforce the obstetric-link invariants for a nursing record (OB-5).

    * a gestation may only be cited by an ``obstetric`` record;
    * the cited gestation must belong to the SAME patient (422 — never a silent
      cross-patient link), and must exist (404).
    """
    if pregnancy_id is None:
        if category == NursingCareCategory.obstetric:
            return  # obstetric without a (known) gestation is allowed
        return
    if category != NursingCareCategory.obstetric:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pregnancy_id is only valid for a record with category='obstetric'.",
        )
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if pregnancy.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pregnancy does not belong to this patient.",
        )


@router.get("/patients/{patient_id}/nursing-care", response_model=list[NursingCareDto])
async def list_nursing_care(
    patient_id: uuid.UUID,
    category: NursingCareCategory | None = Query(
        default=None, description="Optional filter: only records of this category."
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List a patient's nursing-care records, newest care first (OB-5).

    Ordered by ``occurred_at`` desc (the instant the care happened) — the record
    is a snapshot of its date, so the timeline reads by when the care occurred.
    """
    await require_patient_access(patient_id, user, db)
    stmt = select(NursingCare).where(
        NursingCare.patient_id == patient_id,
        NursingCare.is_deleted == False,  # noqa: E712
    )
    if category is not None:
        stmt = stmt.where(NursingCare.category == category.value)
    result = await db.execute(stmt.order_by(NursingCare.occurred_at.desc(), NursingCare.created_at.desc()))
    return result.scalars().all()


@router.post(
    "/patients/{patient_id}/nursing-care",
    response_model=NursingCareDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_nursing_care(
    patient_id: uuid.UUID,
    body: NursingCareCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    await _validate_gestation(db, patient_id, body.category.value, body.pregnancy_id)
    record = NursingCare(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/nursing-care/{record_id}", response_model=NursingCareDto)
async def get_nursing_care(
    record_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NursingCare, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(record.patient_id, user, db)
    return record


@router.patch("/nursing-care/{record_id}", response_model=NursingCareDto)
async def update_nursing_care(
    record_id: uuid.UUID,
    body: NursingCareUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NursingCare, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(record.patient_id, user, db, AccessLevel.contribute)

    changes = body.model_dump(exclude_unset=True)
    # Validate against the *effective* values, so flipping only the category (or
    # only clearing the gestation) can never leave an incoherent record behind.
    effective_category = changes.get("category", record.category)
    if hasattr(effective_category, "value"):
        effective_category = effective_category.value
    effective_pregnancy = changes.get("pregnancy_id", record.pregnancy_id)
    await _validate_gestation(db, record.patient_id, effective_category, effective_pregnancy)

    for field, value in changes.items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/nursing-care/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_nursing_care(
    record_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NursingCare, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(record.patient_id, user, db, AccessLevel.contribute)
    record.is_deleted = True
    await db.commit()
