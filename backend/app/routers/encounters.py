import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.calendar import CalendarEvent
from app.models.document import DocumentReference
from app.models.encounter import Encounter
from app.models.encounter_condition import EncounterCondition
from app.models.encounter_version import EncounterVersion
from app.models.observation import Observation
from app.models.prescription import PRESCRIBER_SINGLETON_ID, Prescriber, Prescription
from app.models.user import User
from app.schemas.calendar import CalendarEventDto
from app.schemas.encounter import (
    EncounterCreateRequest,
    EncounterDto,
    EncounterLinkRequest,
    EncounterUpdateRequest,
    FollowUpCreateRequest,
)
from app.services.encounter_diagnoses import sync_encounter_diagnoses
from app.services.encounter_seal import content_hash, snapshot_from_encounter

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
    data = body.model_dump()
    measurements = data.pop("measurements", [])
    diagnoses = data.pop("diagnoses", [])
    encounter = Encounter(patient_id=patient_id, owner_id=user.id, **data)
    if encounter.prescriber_id is None:
        # WS-6: attribute the note to the configured Prescriber singleton when
        # the client did not choose one, so the responsible professional (and
        # council) is always renderable.
        singleton = await db.get(Prescriber, PRESCRIBER_SINGLETON_ID)
        if singleton is not None and not singleton.is_deleted:
            encounter.prescriber_id = singleton.id
    db.add(encounter)
    await db.flush()  # assign encounter.id before writing its linked vitals/diagnoses
    _add_measurements(db, patient_id, user.id, encounter.id, encounter.encounter_date, measurements)
    if diagnoses:
        await sync_encounter_diagnoses(db, encounter, user.id, diagnoses)
    await db.commit()
    return await _reload(db, encounter.id)


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
    data = body.model_dump(exclude_unset=True)
    measurements = data.pop("measurements", None)
    diagnoses = data.pop("diagnoses", None)
    for field, value in data.items():
        setattr(encounter, field, value)
    if measurements is not None:
        # Replace the vitals recorded in this consultation: soft-delete the old
        # rows and write the new set, so history stays a clean single record.
        existing = (
            await db.execute(
                select(Observation).where(Observation.encounter_id == encounter.id, Observation.is_deleted == False)  # noqa: E712
            )
        ).scalars().all()
        for obs in existing:
            obs.is_deleted = True
        _add_measurements(db, encounter.patient_id, user.id, encounter.id, encounter.encounter_date, measurements)
    if diagnoses is not None:
        # Reconcile the diagnosis links: dropped ones are un-linked (the
        # Condition itself survives as a problem), new ones are added.
        await sync_encounter_diagnoses(db, encounter, user.id, diagnoses)
    await db.commit()
    return await _reload(db, encounter.id)


@router.post("/encounters/{encounter_id}/sign", response_model=EncounterDto)
async def sign_encounter(
    encounter_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seal the current note into an immutable EncounterVersion (WS-6).

    Takes a deterministic snapshot of the note (fields + diagnoses), hashes it
    with SHA-256 and appends a new version. Re-signing appends ``version + 1``;
    editing the note never mutates an existing version.
    """
    result = await db.execute(select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False))  # noqa: E712
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)

    content = snapshot_from_encounter(encounter)
    last_version = (
        await db.execute(
            select(func.max(EncounterVersion.version)).where(EncounterVersion.encounter_id == encounter.id)
        )
    ).scalar()
    prescriber = encounter.prescriber
    db.add(
        EncounterVersion(
            encounter_id=encounter.id,
            version=(last_version or 0) + 1,
            content_hash=content_hash(content),
            content=content,
            signed_at=datetime.now(UTC),
            signed_by=user.id,
            owner_id=user.id,
            professional_name=encounter.prescriber_name,
            board_code=prescriber.board_code if prescriber else None,
            board_number=prescriber.board_number if prescriber else None,
            board_state=prescriber.board_state if prescriber else None,
        )
    )
    await db.commit()
    return await _reload(db, encounter.id)


@router.post("/encounters/{encounter_id}/follow-up", response_model=CalendarEventDto, status_code=status.HTTP_201_CREATED)
async def schedule_follow_up(
    encounter_id: uuid.UUID,
    body: FollowUpCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Schedule a return appointment from this consultation (WS-10).

    Creates a ``CalendarEvent`` (category=appointment) linked to the encounter
    through ``encounter_id``, so the return shows up on the calendar and reads
    back on the consultation as part of its continuity of care.
    """
    result = await db.execute(select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False))  # noqa: E712
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)
    event = CalendarEvent(
        patient_id=encounter.patient_id,
        owner_id=user.id,
        title=(body.title or "").strip() or "Retorno",
        category="appointment",
        start_at=body.start_at,
        end_at=body.end_at,
        purpose=body.purpose,
        source="encounter",
        encounter_id=encounter.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def _apply_link(
    db: AsyncSession, encounter: Encounter, body: EncounterLinkRequest, *, link: bool
) -> None:
    """Set (or clear) ``encounter_id`` on the resource named by *body* (WS-8).

    Only a resource of the SAME patient may be linked: a cross-patient link is a
    422, never a silent success. ``link=False`` detaches (sets the FK to null).
    Ownership never moves — the prescription router and the document vault keep
    owning their rows; only the optional back-reference changes.
    """
    target = encounter.id if link else None
    if body.prescription_id is not None:
        rx = await db.get(Prescription, body.prescription_id)
        if rx is None or rx.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if rx.patient_id != encounter.patient_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="prescription_id does not belong to this patient",
            )
        rx.encounter_id = target
        return
    doc = await db.get(DocumentReference, body.document_id)
    if doc is None or doc.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if doc.patient_id != encounter.patient_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="document_id does not belong to this patient",
        )
    doc.encounter_id = target


async def _load_encounter_for_link(db: AsyncSession, encounter_id: uuid.UUID) -> Encounter:
    result = await db.execute(
        select(Encounter).where(Encounter.id == encounter_id, Encounter.is_deleted == False)  # noqa: E712
    )
    encounter = result.scalar_one_or_none()
    if not encounter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return encounter


@router.post("/encounters/{encounter_id}/link", response_model=EncounterDto)
async def link_encounter_resource(
    encounter_id: uuid.UUID,
    body: EncounterLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link an existing prescription or exam (document) to this consultation (WS-8).

    Recovers "what was prescribed and which exams were requested/interpreted in
    this attendance" straight from the consultation. ``prescription_id`` links a
    Prescription; ``document_id`` links an exam (DocumentReference — the report
    whose analytes are its Observation rows). The resource must belong to the
    same patient, else 422.
    """
    encounter = await _load_encounter_for_link(db, encounter_id)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)
    await _apply_link(db, encounter, body, link=True)
    await db.commit()
    return await _reload(db, encounter.id)


@router.post("/encounters/{encounter_id}/unlink", response_model=EncounterDto)
async def unlink_encounter_resource(
    encounter_id: uuid.UUID,
    body: EncounterLinkRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Detach a prescription or exam from this consultation (WS-8).

    Soft-unlink only: the FK is cleared, the prescription/exam itself survives
    (it simply no longer belongs to this attendance).
    """
    encounter = await _load_encounter_for_link(db, encounter_id)
    await require_patient_access(encounter.patient_id, user, db, AccessLevel.contribute)
    await _apply_link(db, encounter, body, link=False)
    await db.commit()
    return await _reload(db, encounter.id)


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
    vitals = (
        await db.execute(
            select(Observation).where(Observation.encounter_id == encounter.id, Observation.is_deleted == False)  # noqa: E712
        )
    ).scalars().all()
    for obs in vitals:
        obs.is_deleted = True
    # Un-link the diagnoses too; the Conditions themselves (the problem list) stay.
    links = (
        await db.execute(
            select(EncounterCondition).where(
                EncounterCondition.encounter_id == encounter.id, EncounterCondition.is_deleted == False  # noqa: E712
            )
        )
    ).scalars().all()
    for link in links:
        link.is_deleted = True
    await db.commit()


def _add_measurements(db, patient_id, owner_id, encounter_id, encounter_date, measurements):
    """Write the vitals captured in a consultation as linked Observation rows.

    WS-4: systolic and diastolic readings belong to one blood-pressure panel and
    must share a ``component_group_id``. If the client sent one we honour it;
    otherwise a single id is minted for the pair captured in this encounter
    (every measurement here shares the same ``effective_date_time``).
    """
    bp_codes = {"blood-pressure-systolic", "blood-pressure-diastolic"}
    bp_present = {m["code"] for m in measurements if m.get("code") in bp_codes}
    bp_pair = bp_codes <= bp_present
    explicit = next(
        (
            m.get("component_group_id")
            for m in measurements
            if m.get("code") in bp_codes and m.get("component_group_id")
        ),
        None,
    )
    bp_group = explicit or (uuid.uuid4() if bp_pair else None)

    for m in measurements:
        group_id = m.get("component_group_id")
        if m.get("code") in bp_codes and group_id is None and bp_pair:
            group_id = bp_group
        db.add(
            Observation(
                patient_id=patient_id,
                owner_id=owner_id,
                category="measurement",
                encounter_id=encounter_id,
                effective_date_time=encounter_date,
                component_group_id=group_id,
                code=m["code"],
                code_display=m.get("code_display"),
                value_quantity=m.get("value_quantity"),
                value_unit=m.get("value_unit"),
            )
        )


async def _reload(db: AsyncSession, encounter_id: uuid.UUID) -> Encounter:
    """Re-select the encounter so its `measurements` relationship is re-loaded.

    `populate_existing` is required: without it SQLAlchemy returns the already
    identity-mapped Encounter with its stale `measurements` collection, so a
    patch that replaced the vitals would still report the old rows.
    """
    result = await db.execute(
        select(Encounter)
        .where(Encounter.id == encounter_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()