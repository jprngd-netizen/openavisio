import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.encounter import Encounter
from app.models.observation import Observation
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
    data = body.model_dump()
    measurements = data.pop("measurements", [])
    encounter = Encounter(patient_id=patient_id, owner_id=user.id, **data)
    db.add(encounter)
    await db.flush()  # assign encounter.id before writing its linked vitals
    _add_measurements(db, patient_id, user.id, encounter.id, encounter.encounter_date, measurements)
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
    await db.commit()


def _add_measurements(db, patient_id, owner_id, encounter_id, encounter_date, measurements):
    """Write the vitals captured in a consultation as linked Observation rows."""
    for m in measurements:
        db.add(
            Observation(
                patient_id=patient_id,
                owner_id=owner_id,
                category="measurement",
                encounter_id=encounter_id,
                effective_date_time=encounter_date,
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