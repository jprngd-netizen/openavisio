"""Clinical safety summary for the chart cover (WS-9).

A single aggregated, read-only endpoint so the cover banner shows the three
facts that matter at a glance — active allergies, currently-effective
medications, active problems — without three round-trips.

It reuses the WS-1/WS-2/WS-3 domain rules rather than re-implementing them:
``AllergyClinicalStatus.active`` gates allergies, :func:`active_medications`
(status + validity window) gates medications, and ``Condition.clinical_status``
gates problems. No new contract on the existing CRUD routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import require_patient_access
from app.core.database import get_db
from app.core.datetimes import SAO_PAULO
from app.deps import get_current_user
from app.models.allergy import Allergy, AllergyClinicalStatus
from app.models.condition import Condition
from app.models.medication import MedicationStatement
from app.models.user import User
from app.schemas.safety import (
    SafetyAllergyDto,
    SafetyConditionDto,
    SafetyMedicationDto,
    SafetySummaryDto,
)
from app.services.medication_reconciliation import active_medications

router = APIRouter()

# The Condition clinical status that means "a current problem".
ACTIVE_CONDITION_STATUS = "active"


@router.get("/patients/{patient_id}/safety-summary", response_model=SafetySummaryDto)
async def get_safety_summary(
    patient_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Active allergies + active medications + active problems, in one call.

    Only *active* records on every axis: an inactive/resolved allergy, a
    stopped or out-of-window medication, and an inactive/resolved problem are
    all excluded — the banner must never raise a stale alarm.
    """
    await require_patient_access(patient_id, user, db)

    allergies = (
        await db.execute(
            select(Allergy)
            .where(
                Allergy.patient_id == patient_id,
                Allergy.is_deleted == False,  # noqa: E712
                Allergy.clinical_status == AllergyClinicalStatus.active,
            )
            .order_by(Allergy.created_at)
        )
    ).scalars().all()

    meds = (
        await db.execute(
            select(MedicationStatement)
            .where(
                MedicationStatement.patient_id == patient_id,
                MedicationStatement.is_deleted == False,  # noqa: E712
            )
            .order_by(MedicationStatement.created_at)
        )
    ).scalars().all()
    active_meds = active_medications(meds, datetime.now(SAO_PAULO))

    conditions = (
        await db.execute(
            select(Condition)
            .where(
                Condition.patient_id == patient_id,
                Condition.is_deleted == False,  # noqa: E712
                Condition.clinical_status == ACTIVE_CONDITION_STATUS,
            )
            .order_by(Condition.created_at)
        )
    ).scalars().all()

    return SafetySummaryDto(
        allergies=[SafetyAllergyDto.model_validate(a) for a in allergies],
        medications=[SafetyMedicationDto.model_validate(m) for m in active_meds],
        conditions=[SafetyConditionDto.model_validate(c) for c in conditions],
    )
