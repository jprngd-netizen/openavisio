import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.pregnancy import Pregnancy, PregnancyStatus, PregnancyVisit
from app.models.user import User
from app.schemas.pregnancy import (
    GestationalAgeDto,
    ObstetricSummaryDto,
    PregnancyCreateRequest,
    PregnancyDto,
    PregnancyUpdateRequest,
    PregnancyVisitCreateRequest,
    PregnancyVisitDto,
    PregnancyVisitUpdateRequest,
)
from app.services.gestation import display_gestational_age, naegele_due_date

router = APIRouter()

# Episodes that count as a pregnancy *loss* for the derived GOP (OB-DEC-1).
_LOSS_STATUSES = (
    PregnancyStatus.miscarriage.value,
    PregnancyStatus.terminated.value,
    PregnancyStatus.ectopic.value,
)


async def _visit_count(db: AsyncSession, pregnancy_id: uuid.UUID) -> int:
    """Number of live prenatal visits for one episode (OB-2)."""
    result = await db.execute(
        select(func.count())
        .select_from(PregnancyVisit)
        .where(
            PregnancyVisit.pregnancy_id == pregnancy_id,
            PregnancyVisit.is_deleted == False,  # noqa: E712
        )
    )
    return int(result.scalar_one())


async def _load_pregnancy_for_patient(
    db: AsyncSession, patient_id: uuid.UUID, pregnancy_id: uuid.UUID
) -> Pregnancy:
    """Fetch an episode and enforce it belongs to ``patient_id``.

    A visit may only be recorded against the episode of the same patient; a
    mismatch is a client error (422), not a silent cross-patient write.
    """
    pregnancy = await db.get(Pregnancy, pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if pregnancy.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pregnancy does not belong to this patient.",
        )
    return pregnancy


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
    pregnancies = result.scalars().all()
    # OB-2: expose the visit count per episode in one grouped query.
    counts = await db.execute(
        select(PregnancyVisit.pregnancy_id, func.count())
        .where(
            PregnancyVisit.pregnancy_id.in_([p.id for p in pregnancies]),
            PregnancyVisit.is_deleted == False,  # noqa: E712
        )
        .group_by(PregnancyVisit.pregnancy_id)
    )
    visit_counts = {row[0]: row[1] for row in counts.all()}
    return [
        PregnancyDto.from_model(p, as_of=as_of, visit_count=visit_counts.get(p.id, 0))
        for p in pregnancies
    ]


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
    return PregnancyDto.from_model(
        pregnancy, as_of=as_of, visit_count=await _visit_count(db, pregnancy.id)
    )


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
    return PregnancyDto.from_model(
        pregnancy, visit_count=await _visit_count(db, pregnancy.id)
    )


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


# ------------------------------- Prenatal visits (OB-2) -------------------------------
# A visit belongs to one episode. The nested routes take patient_id to enforce
# that the episode is the *same* patient's; reading a single visit by its own id
# resolves the patient through the episode.


@router.get(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/visits",
    response_model=list[PregnancyVisitDto],
)
async def list_pregnancy_visits(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    result = await db.execute(
        select(PregnancyVisit)
        .where(
            PregnancyVisit.pregnancy_id == pregnancy_id,
            PregnancyVisit.is_deleted == False,  # noqa: E712
        )
        .order_by(PregnancyVisit.visit_date.asc(), PregnancyVisit.created_at.asc())
    )
    return [PregnancyVisitDto.from_model(v, pregnancy=pregnancy) for v in result.scalars().all()]


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/visits",
    response_model=PregnancyVisitDto,
    status_code=status.HTTP_201_CREATED,
)
async def create_pregnancy_visit(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: PregnancyVisitCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    visit = PregnancyVisit(
        pregnancy_id=pregnancy_id, owner_id=user.id, **body.model_dump()
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return PregnancyVisitDto.from_model(visit, pregnancy=pregnancy)


@router.get("/pregnancy-visits/{visit_id}", response_model=PregnancyVisitDto)
async def get_pregnancy_visit(
    visit_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    visit = await db.get(PregnancyVisit, visit_id)
    if not visit or visit.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pregnancy = await db.get(Pregnancy, visit.pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db)
    return PregnancyVisitDto.from_model(visit, pregnancy=pregnancy)


@router.patch("/pregnancy-visits/{visit_id}", response_model=PregnancyVisitDto)
async def update_pregnancy_visit(
    visit_id: uuid.UUID,
    body: PregnancyVisitUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    visit = await db.get(PregnancyVisit, visit_id)
    if not visit or visit.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pregnancy = await db.get(Pregnancy, visit.pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db, AccessLevel.contribute)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(visit, field, value)
    await db.commit()
    await db.refresh(visit)
    return PregnancyVisitDto.from_model(visit, pregnancy=pregnancy)


@router.delete("/pregnancy-visits/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pregnancy_visit(
    visit_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    visit = await db.get(PregnancyVisit, visit_id)
    if not visit or visit.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pregnancy = await db.get(Pregnancy, visit.pregnancy_id)
    if not pregnancy or pregnancy.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(pregnancy.patient_id, user, db, AccessLevel.contribute)
    visit.is_deleted = True
    await db.commit()
