import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


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