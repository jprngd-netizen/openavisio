import uuid
from datetime import date as _date
from datetime import datetime

from pydantic import BaseModel

from app.models.referral import ReferralStatus
from app.schemas.common import OrmBase


class ReferralDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    target_specialty: str
    reason: str | None
    status: str
    # the field is named ``date`` on the wire; the type is aliased so the field
    # name does not shadow ``datetime.date`` during annotation evaluation.
    date: _date | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class ReferralCreateRequest(BaseModel):
    target_specialty: str
    encounter_id: uuid.UUID | None = None
    reason: str | None = None
    status: ReferralStatus = ReferralStatus.draft
    date: _date | None = None
    note: str | None = None


class ReferralUpdateRequest(BaseModel):
    target_specialty: str | None = None
    encounter_id: uuid.UUID | None = None
    reason: str | None = None
    status: ReferralStatus | None = None
    date: _date | None = None
    note: str | None = None
