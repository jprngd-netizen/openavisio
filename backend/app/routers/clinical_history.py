import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import AccessLevel, require_patient_access
from app.core.database import get_db
from app.deps import get_current_user
from app.models.clinical_history import ClinicalHistory
from app.models.user import User
from app.schemas.clinical_history import ClinicalHistoryDto, ClinicalHistoryUpsert

router = APIRouter()


async def _get(db: AsyncSession, patient_id: uuid.UUID) -> ClinicalHistory | None:
    return (await db.execute(
        select(ClinicalHistory).where(
            ClinicalHistory.patient_id == patient_id, ClinicalHistory.is_deleted == False  # noqa: E712
        )
    )).scalar_one_or_none()


@router.get("/patients/{patient_id}/clinical-history", response_model=ClinicalHistoryDto | None)
async def get_clinical_history(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db)
    return await _get(db, patient_id)


@router.put("/patients/{patient_id}/clinical-history", response_model=ClinicalHistoryDto)
async def upsert_clinical_history(
    patient_id: uuid.UUID,
    body: ClinicalHistoryUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_patient_access(patient_id, user, db, AccessLevel.contribute)
    record = await _get(db, patient_id)
    if record is None:
        record = ClinicalHistory(patient_id=patient_id)
        db.add(record)
    data = body.model_dump()
    for field, value in data.items():
        setattr(record, field, value)
    await db.commit()
    await db.refresh(record)
    return record
