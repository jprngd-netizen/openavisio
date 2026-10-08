import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase


class EmploymentItem(BaseModel):
    company: str | None = None
    role: str | None = None
    start: str | None = None
    end: str | None = None


class ExposureItem(BaseModel):
    category: str | None = None  # physical | chemical | biological | ergonomic | psychosocial
    agent: str | None = None
    duration: str | None = None
    ppe: bool | None = None


class ClinicalHistoryDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    personal_history: str | None = None
    family_history: str | None = None
    surgical_history: str | None = None
    allergies: str | None = None
    habits: str | None = None
    previous_employments: list[EmploymentItem] = []
    exposures: list[ExposureItem] = []
    created_at: datetime
    updated_at: datetime


class ClinicalHistoryUpsert(BaseModel):
    personal_history: str | None = None
    family_history: str | None = None
    surgical_history: str | None = None
    allergies: str | None = None
    habits: str | None = None
    previous_employments: list[EmploymentItem] = []
    exposures: list[ExposureItem] = []
