import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class ClinicalHistoryDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    personal_history: str | None = None
    family_history: str | None = None
    surgical_history: str | None = None
    allergies: str | None = None
    habits: str | None = None
    created_at: datetime
    updated_at: datetime


class ClinicalHistoryUpsert(BaseModel):
    personal_history: str | None = None
    family_history: str | None = None
    surgical_history: str | None = None
    allergies: str | None = None
    habits: str | None = None
