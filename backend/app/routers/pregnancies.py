import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.pregnancy import Pregnancy, PregnancyStatus
from app.models.user import User
from app.schemas.pregnancy import (
    GestationalAgeDto,
    ObstetricSummaryDto,
    PregnancyCreateRequest,
    PregnancyDto,
    PregnancyUpdateRequest,
)
from app.services.gestation import display_gestational_age, naegele_due_date

router = APIRouter()

# Episodes that count as a pregnancy *loss* for the derived GOP (OB-DEC-1).
_LOSS_STATUSES = (
    PregnancyStatus.miscarriage.value,
    PregnancyStatus.terminated.value,
    PregnancyStatus.ectopic.value,
)


@router.get("/patients/{patient_id}/pregnancies", response_model=list[PregnancyDto])
async def list_pregnancies(
    patient_id: uuid.UUID,
    as_of: date | None = Query(
        default=None,
        description="Live reference date for the gestational age of ACTIVE episodes "
        "(never defaulted server-side). Ended episodes ignore it.",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    result = await db.execute(
        select(Pregnancy)
        .where(
            Pregnancy.patient_id == patient_id,
            Pregnancy.is_deleted == False,  # noqa: E712
        )
        .order_by(Pregnancy.lmp_date.desc().nullslast(), Pregnancy.created_at.desc())
    )
    return [PregnancyDto.from_model(p, as_of=as_of) for p in result.scalars().all()]


@router.post(
    "/patients/{patient_id}/pregnancies",
    response_model=PregnancyDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_pregnancy(
    patient_id: uuid.UUID,
    body: PregnancyCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = Pregnancy(patient_id=patient_id, owner_id=user.id, **body.model_dump())
    db.add(pregnancy)
    await db.commit()
    await db.refresh(pregnancy)
    return PregnancyDto.from_model(pregnancy)


@router.get("/pregnancies/{pregnancy_id}", response_model=PregnancyDto)
async def get_pregnancy(
    pregnancy_id: uuid.UUID,
    as_of: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db)
    return PregnancyDto.from_model(pregnancy, as_of=as_of)


@router.patch("/pregnancies/{pregnancy_id}", response_model=PregnancyDto)
async def update_pregnancy(
    pregnancy_id: uuid.UUID,
    body: PregnancyUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db, AccessLevel.contribute)

    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(pregnancy, field, value)
    # Keep the stored Naegele DPP consistent with a newly informed DUM, unless
    # the caller set an explicit DPP in the same request.
    if "lmp_date" in changes and "estimated_due_date" not in changes and pregnancy.lmp_date is not None:
        pregnancy.estimated_due_date = naegele_due_date(pregnancy.lmp_date)
    await db.commit()
    await db.refresh(pregnancy)
    return PregnancyDto.from_model(pregnancy)


@router.delete("/pregnancies/{pregnancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pregnancy(
    pregnancy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db, AccessLevel.contribute)
    pregnancy.is_deleted = True
    await db.commit()


@router.get("/pregnancies/{pregnancy_id}/gestational-age", response_model=GestationalAgeDto)
async def pregnancy_gestational_age(
    pregnancy_id: uuid.UUID,
    as_of: date = Query(..., description="The date the age is computed for (required)."),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gestational age on an explicit date — the record is a snapshot of `as_of`."""
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db)
    ga = display_gestational_age(pregnancy, as_of=as_of)
    if ga is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No dating basis: the episode has no LMP and no ultrasound-corrected DPP.",
        )
    return GestationalAgeDto(
        weeks=ga.weeks, days=ga.days, total_days=ga.total_days, as_of=ga.as_of, basis=ga.basis
    )


@router.get("/patients/{patient_id}/obstetric-summary", response_model=ObstetricSummaryDto)
async def obstetric_summary(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Derived GOP (OB-DEC-1): G = all episodes, P = delivered, A = losses."""
    await require_patient_access(patient_id, user, db)
    rows = await db.execute(
        select(Pregnancy.status, func.count())
        .where(
            Pregnancy.patient_id == patient_id,
            Pregnancy.is_deleted == False,  # noqa: E712
        )
        .group_by(Pregnancy.status)
    )
    counts = {row[0]: row[1] for row in rows.all()}
    gravida = sum(counts.values())
    para = counts.get(PregnancyStatus.completed.value, 0)
    aborto = sum(counts.get(s, 0) for s in _LOSS_STATUSES)
    return ObstetricSummaryDto(gravida=gravida, para=para, aborto=aborto)
