import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.newborn_record import NewbornRecord
from app.models.pregnancy import LIVE_BIRTH_OUTCOMES, Pregnancy, PregnancyOutcome
from app.models.user import User
from app.schemas.newborn_record import (
    NewbornRecordCreateRequest,
    NewbornRecordDto,
    NewbornRecordUpdateRequest,
)

router = APIRouter()


async def _load_outcome_for_patient(
    db: AsyncSession, patient_id: uuid.UUID, pregnancy_id: uuid.UUID
) -> PregnancyOutcome:
    """Fetch the episode's outcome, enforcing same-patient + live outcome.

    The newborn record hangs off the *outcome* (1:1), so the episode must belong
    to ``patient_id`` (a mismatch is a client error — 422, never a silent
    cross-patient write) and must already carry a live outcome (404 otherwise);
    a newborn cannot precede the outcome that closes the episode.
    """
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if pregnancy.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pregnancy does not belong to this patient.",
        )
    outcome = (
        await db.execute(
            select(PregnancyOutcome).where(
                PregnancyOutcome.pregnancy_id == pregnancy_id,
                PregnancyOutcome.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outcome recorded for this pregnancy.",
        )
    return outcome


async def _load_any_record(db: AsyncSession, outcome_id: uuid.UUID) -> NewbornRecord | None:
    """The single newborn record row of an outcome, deleted or not.

    The 1:1 unique constraint is a database invariant that a soft-delete does not
    release, so the create path must see the row even when it is soft-deleted (to
    reactivate it) rather than attempt a second INSERT.
    """
    result = await db.execute(
        select(NewbornRecord).where(NewbornRecord.pregnancy_outcome_id == outcome_id)
    )
    return result.scalar_one_or_none()


async def _load_record(db: AsyncSession, outcome_id: uuid.UUID) -> NewbornRecord | None:
    """The (single) live newborn record of an outcome, or ``None``."""
    record = await _load_any_record(db, outcome_id)
    if record is None or record.is_deleted:
        return None
    return record


async def _patient_of_record(db: AsyncSession, record: NewbornRecord) -> uuid.UUID:
    """Resolve the owning patient of a newborn record through its outcome.

    Every get/patch/delete on a single record resolves the patient this way, so
    access is always checked against the real owner (a record never carries a
    patient_id of its own — it is 1:1 with the outcome).
    """
    outcome = await db.get(PregnancyOutcome, record.pregnancy_outcome_id)
    if not outcome or outcome.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pregnancy = await db.get(Pregnancy, outcome.pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return pregnancy.patient_id


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/outcome/newborn",
    response_model=NewbornRecordDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_newborn_record(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: NewbornRecordCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open the newborn record of a closed episode (FExEO-SUS I.2/I.3).

    The record is 1:1 with the outcome: a second registration for the same
    outcome is a client conflict (409).
    """
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    outcome = await _load_outcome_for_patient(db, patient_id, pregnancy_id)
    # A newborn record only exists for a live birth: the episode must have closed
    # with a vaginal or cesarean delivery (a loss never carries RN data).
    if outcome.outcome_type not in LIVE_BIRTH_OUTCOMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A newborn record is only valid for a live-birth outcome.",
        )
    if await _load_record(db, outcome.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A newborn record is already recorded for this outcome.",
        )
    # A soft-deleted record still holds the 1:1 unique constraint, so re-opening
    # the record for this outcome revives it instead of attempting a second row.
    existing = await _load_any_record(db, outcome.id)
    if existing is not None:
        for field, value in body.model_dump().items():
            setattr(existing, field, value)
        existing.is_deleted = False
        await db.commit()
        await db.refresh(existing)
        return existing
    record = NewbornRecord(pregnancy_outcome_id=outcome.id, owner_id=user.id, **body.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/outcome/newborn",
    response_model=NewbornRecordDto,
)
async def get_newborn_record_for_outcome(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    outcome = await _load_outcome_for_patient(db, patient_id, pregnancy_id)
    record = await _load_record(db, outcome.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return record


@router.get("/newborn-records/{record_id}", response_model=NewbornRecordDto)
async def get_newborn_record(
    record_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NewbornRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(await _patient_of_record(db, record), user, db)
    return record


@router.patch("/newborn-records/{record_id}", response_model=NewbornRecordDto)
async def update_newborn_record(
    record_id: uuid.UUID,
    body: NewbornRecordUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NewbornRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(
        await _patient_of_record(db, record), user, db, AccessLevel.contribute
    )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/newborn-records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_newborn_record(
    record_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await db.get(NewbornRecord, record_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(
        await _patient_of_record(db, record), user, db, AccessLevel.contribute
    )
    record.is_deleted = True
    await db.commit()
