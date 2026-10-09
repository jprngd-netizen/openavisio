import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.allergy import AllergyClinicalStatus, AllergyCriticality, AllergySeverity
from app.schemas.common import OrmBase, TzDateTime


class AllergyDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    substance_code: str | None
    substance_display: str
    reaction: str | None
    severity: str | None
    onset: TzDateTime | None
    criticality: str
    clinical_status: str
    note: str | None
    created_at: datetime
    updated_at: datetime


class AllergyCreateRequest(BaseModel):
    substance_code: str | None = None
    substance_display: str
    reaction: str | None = None
    severity: AllergySeverity | None = None
    onset: TzDateTime | None = None
    criticality: AllergyCriticality = AllergyCriticality.unable_to_assess
    clinical_status: AllergyClinicalStatus = AllergyClinicalStatus.active
    note: str | None = None


class AllergyUpdateRequest(BaseModel):
    substance_code: str | None = None
    substance_display: str | None = None
    reaction: str | None = None
    severity: AllergySeverity | None = None
    onset: TzDateTime | None = None
    criticality: AllergyCriticality | None = None
    clinical_status: AllergyClinicalStatus | None = None
    note: str | None = None


class AllergyConflictDto(BaseModel):
    allergy_id: uuid.UUID
    substance_display: str
    reaction: str | None
    severity: str | None
    criticality: str
    matched_substance: str
