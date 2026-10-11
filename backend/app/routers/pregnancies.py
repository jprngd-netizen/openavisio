import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.document import DocumentReference
from app.models.observation import Observation
from app.models.pregnancy import (
    OUTCOME_STATUS,
    Pregnancy,
    PregnancyCondition,
    PregnancyOutcome,
    PregnancyStatus,
    PregnancyVisit,
)
from app.models.user import User
from app.schemas.encounter import LinkedExamDto
from app.schemas.observation import ObservationDto
from app.schemas.pregnancy import (
    GestationalAgeDto,
    ObstetricSummaryDto,
    PregnancyConditionDto,
    PregnancyConditionInput,
    PregnancyCreateRequest,
    PregnancyDto,
    PregnancyLinkRequest,
    PregnancyOutcomeCreateRequest,
    PregnancyOutcomeDto,
    PregnancyUpdateRequest,
    PregnancyVisitCreateRequest,
    PregnancyVisitDto,
    PregnancyVisitUpdateRequest,
)
from app.services.encounter_diagnoses import resolve_condition
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


async def _load_outcome(db: AsyncSession, pregnancy_id: uuid.UUID) -> PregnancyOutcome | None:
    """The (single) live outcome of an episode, or ``None`` while open (OB-3)."""
    result = await db.execute(
        select(PregnancyOutcome).where(
            PregnancyOutcome.pregnancy_id == pregnancy_id,
            PregnancyOutcome.is_deleted == False,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def _load_conditions(db: AsyncSession, pregnancy_id: uuid.UUID) -> list[PregnancyCondition]:
    """Intercorrências (linked Conditions) of an episode, oldest first (OB-4)."""
    result = await db.execute(
        select(PregnancyCondition)
        .where(
            PregnancyCondition.pregnancy_id == pregnancy_id,
            PregnancyCondition.is_deleted == False,  # noqa: E712
        )
        .order_by(PregnancyCondition.created_at.asc())
    )
    return list(result.scalars().all())


async def _load_vitals(db: AsyncSession, pregnancy_id: uuid.UUID) -> list[Observation]:
    """Vitals (Observations) attributed to an episode, oldest first (OB-4)."""
    result = await db.execute(
        select(Observation)
        .where(
            Observation.pregnancy_id == pregnancy_id,
            Observation.is_deleted == False,  # noqa: E712
        )
        .order_by(Observation.effective_date_time.asc().nullsfirst(), Observation.created_at.asc())
    )
    return list(result.scalars().all())


async def _load_exams(db: AsyncSession, pregnancy_id: uuid.UUID) -> list[DocumentReference]:
    """Exams (DocumentReferences) attributed to an episode, newest first (OB-4)."""
    result = await db.execute(
        select(DocumentReference)
        .where(
            DocumentReference.pregnancy_id == pregnancy_id,
            DocumentReference.is_deleted == False,  # noqa: E712
        )
        .order_by(DocumentReference.created_at.desc())
    )
    return list(result.scalars().all())


async def _pregnancy_dto(db: AsyncSession, pregnancy: Pregnancy, *, as_of=None) -> PregnancyDto:
    """Build the full DTO for one episode, with its OB-2/OB-3/OB-4 children."""
    return PregnancyDto.from_model(
        pregnancy,
        as_of=as_of,
        visit_count=await _visit_count(db, pregnancy.id),
        outcome=await _load_outcome(db, pregnancy.id),
        conditions=[
            PregnancyConditionDto.from_model(link)
            for link in await _load_conditions(db, pregnancy.id)
        ],
        vitals=[
            ObservationDto.model_validate(obs) for obs in await _load_vitals(db, pregnancy.id)
        ],
        exams=[LinkedExamDto.model_validate(doc) for doc in await _load_exams(db, pregnancy.id)],
    )


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
    # OB-3: expose each episode's outcome (if any) in one grouped query too.
    outcomes = await db.execute(
        select(PregnancyOutcome).where(
            PregnancyOutcome.pregnancy_id.in_([p.id for p in pregnancies]),
            PregnancyOutcome.is_deleted == False,  # noqa: E712
        )
    )
    outcome_by_pregnancy = {o.pregnancy_id: o for o in outcomes.scalars().all()}
    # OB-4: expose each episode's intercorrências / linked vitals / linked exams
    # in grouped queries too, so the listing stays O(1) in round-trips.
    ids = [p.id for p in pregnancies]
    cond_rows = (
        await db.execute(
            select(PregnancyCondition).where(
                PregnancyCondition.pregnancy_id.in_(ids),
                PregnancyCondition.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    conditions_by_pregnancy: dict[uuid.UUID, list[PregnancyConditionDto]] = {}
    for link in cond_rows:
        conditions_by_pregnancy.setdefault(link.pregnancy_id, []).append(
            PregnancyConditionDto.from_model(link)
        )
    vital_rows = (
        await db.execute(
            select(Observation).where(
                Observation.pregnancy_id.in_(ids),
                Observation.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    vitals_by_pregnancy: dict[uuid.UUID, list[ObservationDto]] = {}
    for obs in vital_rows:
        if obs.pregnancy_id is None:  # filtered above; guards the type
            continue
        vitals_by_pregnancy.setdefault(obs.pregnancy_id, []).append(
            ObservationDto.model_validate(obs)
        )
    exam_rows = (
        await db.execute(
            select(DocumentReference).where(
                DocumentReference.pregnancy_id.in_(ids),
                DocumentReference.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars().all()
    exams_by_pregnancy: dict[uuid.UUID, list[LinkedExamDto]] = {}
    for doc in exam_rows:
        if doc.pregnancy_id is None:  # filtered above; guards the type
            continue
        exams_by_pregnancy.setdefault(doc.pregnancy_id, []).append(
            LinkedExamDto.model_validate(doc)
        )
    return [
        PregnancyDto.from_model(
            p,
            as_of=as_of,
            visit_count=visit_counts.get(p.id, 0),
            outcome=outcome_by_pregnancy.get(p.id),
            conditions=conditions_by_pregnancy.get(p.id, []),
            vitals=vitals_by_pregnancy.get(p.id, []),
            exams=exams_by_pregnancy.get(p.id, []),
        )
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
    return await _pregnancy_dto(db, pregnancy, as_of=as_of)


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
    return await _pregnancy_dto(db, pregnancy)


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


# ------------------------------- Outcome (OB-3) -------------------------------
# Registering the outcome is the act that CLOSES the episode: the terminal status
# and ``ended_at`` are set from the outcome, and the outcome is 1:1 with the
# episode (a second registration is refused). The record is a snapshot of its
# date — its GA is derived for ``as_of=outcome_date``.


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/outcome",
    response_model=PregnancyDto,
    status_code=status.HTTP_201_CREATED,
)
async def register_pregnancy_outcome(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: PregnancyOutcomeCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    # Idempotency: one outcome per episode. A duplicate is a client conflict.
    if await _load_outcome(db, pregnancy_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An outcome is already recorded for this pregnancy.",
        )
    outcome = PregnancyOutcome(pregnancy_id=pregnancy_id, owner_id=user.id, **body.model_dump())
    db.add(outcome)
    # Closing the episode: adequate terminal status + the outcome's own date.
    pregnancy.status = OUTCOME_STATUS[body.outcome_type].value
    pregnancy.ended_at = body.outcome_date
    await db.commit()
    await db.refresh(pregnancy)
    await db.refresh(outcome)
    return await _pregnancy_dto(db, pregnancy)


@router.get(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/outcome",
    response_model=PregnancyOutcomeDto,
)
async def get_pregnancy_outcome(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    outcome = await _load_outcome(db, pregnancy_id)
    if outcome is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return PregnancyOutcomeDto.from_model(outcome, pregnancy=pregnancy)


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


# --------------------------- Clinical integrations (OB-4) ---------------------------
# Intercorrências are linked Conditions (find-or-created via the WS-3 service, so
# they land in the problem list with a single source of truth); a vital and an
# exam point back at the episode through a nullable FK, exactly as WS-8 did for
# consultations. Everything is same-patient: a cross-patient link is a 422.
_PLACEHOLDER_DISPLAY = "—"


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/conditions",
    response_model=PregnancyDto,
    status_code=status.HTTP_201_CREATED,
)
async def add_pregnancy_condition(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: PregnancyConditionInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record an intercorrência (gestational diagnosis) in the episode (OB-4).

    The problem-list Condition is found-or-created by ``(patient_id, code)``
    through the WS-3 service (reused, never reimplemented), so the same CID-10
    never duplicates. Re-adding a previously removed intercorrência re-activates
    the existing link instead of inserting a second one.
    """
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    code = body.cid10_code or None
    display = body.cid10_display or code or _PLACEHOLDER_DISPLAY
    condition = await resolve_condition(
        db,
        patient_id=patient_id,
        owner_id=user.id,
        code=code,
        code_display=display,
        condition_id=body.condition_id,
    )
    link = (
        await db.execute(
            select(PregnancyCondition).where(
                PregnancyCondition.pregnancy_id == pregnancy_id,
                PregnancyCondition.condition_id == condition.id,
            )
        )
    ).scalar_one_or_none()
    if link is None:
        db.add(
            PregnancyCondition(
                pregnancy_id=pregnancy_id,
                condition_id=condition.id,
                cid10_code=code,
                cid10_display=body.cid10_display,
            )
        )
    else:
        # Re-adding an intercorrência that had been removed: reactivate the link.
        link.is_deleted = False
        link.cid10_code = code
        link.cid10_display = body.cid10_display
    await db.commit()
    await db.refresh(pregnancy)
    return await _pregnancy_dto(db, pregnancy)


@router.delete(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/conditions/{condition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_pregnancy_condition(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    condition_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an intercorrência from the episode (OB-4).

    Soft-deletes only the link; the Condition stays in the problem list (a
    diagnosis is not erased by un-linking it from one gestation).
    """
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    link = (
        await db.execute(
            select(PregnancyCondition).where(
                PregnancyCondition.pregnancy_id == pregnancy_id,
                PregnancyCondition.condition_id == condition_id,
                PregnancyCondition.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    link.is_deleted = True
    await db.commit()


async def _apply_pregnancy_link(
    db: AsyncSession, pregnancy: Pregnancy, body: PregnancyLinkRequest, *, link: bool
) -> None:
    """Set (or clear) ``pregnancy_id`` on the vital/exam named by *body* (OB-4).

    Only a resource of the SAME patient may be linked: a cross-patient link is a
    422, never a silent success. ``link=False`` detaches (sets the FK to null).
    Ownership never moves — the observations router and the document vault keep
    owning their rows; only the optional back-reference changes.
    """
    target = pregnancy.id if link else None
    if body.observation_id is not None:
        obs = await db.get(Observation, body.observation_id)
        if obs is None or obs.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if obs.patient_id != pregnancy.patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="observation_id does not belong to this patient",
            )
        obs.pregnancy_id = target
        return
    doc = await db.get(DocumentReference, body.document_id)
    if doc is None or doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if doc.patient_id != pregnancy.patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_id does not belong to this patient",
        )
    doc.pregnancy_id = target


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/link", response_model=PregnancyDto
)
async def link_pregnancy_resource(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: PregnancyLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attribute an existing vital (Observation) or exam (DocumentReference) to
    the episode (OB-4).

    ``observation_id`` links a vital (category=measurement); ``document_id``
    links an exam — the report whose analytes are its Observation rows. The
    resource must belong to the same patient, else 422.
    """
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    await _apply_pregnancy_link(db, pregnancy, body, link=True)
    await db.commit()
    await db.refresh(pregnancy)
    return await _pregnancy_dto(db, pregnancy)


@router.post(
    "/patients/{patient_id}/pregnancies/{pregnancy_id}/unlink", response_model=PregnancyDto
)
async def unlink_pregnancy_resource(
    patient_id: uuid.UUID,
    pregnancy_id: uuid.UUID,
    body: PregnancyLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detach a vital or exam from the episode (OB-4).

    Soft-unlink only: the FK is cleared, the vital/exam itself survives (it
    simply no longer belongs to this gestation).
    """
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    pregnancy = await _load_pregnancy_for_patient(db, patient_id, pregnancy_id)
    await _apply_pregnancy_link(db, pregnancy, body, link=False)
    await db.commit()
    await db.refresh(pregnancy)
    return await _pregnancy_dto(db, pregnancy)
