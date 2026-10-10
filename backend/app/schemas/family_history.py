import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.family_history import FamilyRelationship
from app.schemas.common import OrmBase


class FamilyHistoryDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    relationship: str
    condition_code: str | None
    condition_display: str
    age_at_onset: int | None
    deceased: bool | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class FamilyHistoryCreateRequest(BaseModel):
    relationship: FamilyRelationship
    condition_code: str | None = None
    condition_display: str
    age_at_onset: int | None = None
    deceased: bool | None = None
    note: str | None = None


class FamilyHistoryUpdateRequest(BaseModel):
    relationship: FamilyRelationship | None = None
    condition_code: str | None = None
    condition_display: str | None = None
    age_at_onset: int | None = None
    deceased: bool | None = None
    note: str | None = None
