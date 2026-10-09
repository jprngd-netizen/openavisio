import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import OrmBase, TzDateTime


class MedicationDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    medication_code: str | None
    medication_display: str
    date_asserted: TzDateTime | None
    effective_start: TzDateTime | None
    effective_end: TzDateTime | None
    dosage_text: str | None
    dose_quantity: float | None
    dose_unit: str | None
    route: str | None
    reason_code: str | None
    note: str | None
    document_reference_id: uuid.UUID | None
    created_at: datetime
    is_active: bool = True


class MedicationCreateRequest(BaseModel):
    status: str = "active"
    medication_code: str | None = None
    medication_display: str
    date_asserted: TzDateTime | None = None
    effective_start: TzDateTime | None = None
    effective_end: TzDateTime | None = None
    dosage_text: str | None = None
    dose_quantity: float | None = None
    dose_unit: str | None = None
    route: str | None = None
    reason_code: str | None = None
    note: str | None = None


class MedicationUpdateRequest(MedicationCreateRequest):
    medication_display: str | None = None


class ActiveMedicationDto(MedicationDto):
    """An active medication plus the ids of active meds it duplicates (WS-2).

    ``duplicate_of`` is empty when the substance is unique among the active
    list; a non-empty list flags a likely double prescription.
    """

    duplicate_of: list[uuid.UUID] = []
