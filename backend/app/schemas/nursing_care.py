import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.nursing_care import NursingCareCategory
from app.schemas.common import OrmBase, TzDateTime


class NursingCareDto(OrmBase):
    """A nursing-care record as read back (OB-5).

    ``occurred_at`` is the instant the care happened — the record is a snapshot
    of that date, never of "today".
    """

    id: uuid.UUID
    patient_id: uuid.UUID
    occurred_at: TzDateTime
    category: str
    pregnancy_id: uuid.UUID | None
    notes: str | None
    performed_by: str | None
    created_at: datetime
    updated_at: datetime


class NursingCareCreateRequest(BaseModel):
    """Create a nursing-care record (OB-5).

    ``occurred_at`` is required: the record is dated, so it cannot be recorded
    without the instant it refers to (no server-side "now" default — the record
    is what was true at that time, not at the time of data entry).
    """

    occurred_at: TzDateTime
    category: NursingCareCategory = NursingCareCategory.general
    pregnancy_id: uuid.UUID | None = None
    notes: str | None = None
    performed_by: str | None = None

    @model_validator(mode="after")
    def _gestation_only_for_obstetric(self) -> "NursingCareCreateRequest":
        # A gestation link only makes sense in the obstetric context; a general
        # record has no episode to annotate.
        if self.pregnancy_id is not None and self.category != NursingCareCategory.obstetric:
            raise ValueError("pregnancy_id is only valid for a record with category='obstetric'")
        return self


class NursingCareUpdateRequest(BaseModel):
    occurred_at: TzDateTime | None = None
    category: NursingCareCategory | None = None
    pregnancy_id: uuid.UUID | None = None
    notes: str | None = None
    performed_by: str | None = None
