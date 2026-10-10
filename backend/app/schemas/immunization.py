import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.immunization import ImmunizationStatus
from app.schemas.common import OrmBase


class ImmunizationDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    vaccine_code: str | None
    vaccine_display: str
    dose_number: int | None
    occurrence_date: date | None
    lot_number: str | None
    route: str | None
    site: str | None
    manufacturer: str | None
    reaction: str | None
    status: str
    note: str | None
    created_at: datetime
    updated_at: datetime


class ImmunizationCreateRequest(BaseModel):
    vaccine_code: str | None = None
    vaccine_display: str
    dose_number: int | None = None
    occurrence_date: date | None = None
    lot_number: str | None = None
    route: str | None = None
    site: str | None = None
    manufacturer: str | None = None
    reaction: str | None = None
    status: ImmunizationStatus = ImmunizationStatus.completed
    note: str | None = None


class ImmunizationUpdateRequest(BaseModel):
    vaccine_code: str | None = None
    vaccine_display: str | None = None
    dose_number: int | None = None
    occurrence_date: date | None = None
    lot_number: str | None = None
    route: str | None = None
    site: str | None = None
    manufacturer: str | None = None
    reaction: str | None = None
    status: ImmunizationStatus | None = None
    note: str | None = None
