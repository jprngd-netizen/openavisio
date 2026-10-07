import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase
from app.schemas.observation import ObservationDto


class EncounterMeasurement(BaseModel):
    """A vital sign captured during the consultation (weight, BP, SpO2, ...)."""

    code: str
    code_display: str | None = None
    value_quantity: float | None = None
    value_unit: str | None = None


class EncounterDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    encounter_type: str | None
    encounter_date: str | None
    chief_complaint: str | None
    history: str | None
    physical_exam: str | None
    assessment: str | None
    plan: str | None
    cid10_code: str | None
    cid10_display: str | None
    notes: str | None
    measurements: list[ObservationDto] = []
    created_at: datetime
    updated_at: datetime


class EncounterCreateRequest(BaseModel):
    status: str = "finished"
    encounter_type: str | None = None
    encounter_date: str | None = None
    chief_complaint: str | None = None
    history: str | None = None
    physical_exam: str | None = None
    assessment: str | None = None
    plan: str | None = None
    cid10_code: str | None = None
    cid10_display: str | None = None
    notes: str | None = None
    measurements: list[EncounterMeasurement] = []


class EncounterUpdateRequest(BaseModel):
    status: str | None = None
    encounter_type: str | None = None
    encounter_date: str | None = None
    chief_complaint: str | None = None
    history: str | None = None
    physical_exam: str | None = None
    assessment: str | None = None
    plan: str | None = None
    cid10_code: str | None = None
    cid10_display: str | None = None
    notes: str | None = None
    measurements: list[EncounterMeasurement] | None = None