import uuid

from pydantic import BaseModel, model_validator

from app.schemas.common import OrmBase, TzDateTime
from app.services.vital_ranges import check_vital


class ObservationDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    code: str | None
    code_display: str | None
    category: str | None
    panel: str | None
    component_group_id: uuid.UUID | None = None
    effective_date_time: TzDateTime | None
    value_quantity: float | None
    value_unit: str | None
    value_string: str | None
    reference_range: str | None
    ref_low: float | None
    ref_high: float | None
    document_reference_id: uuid.UUID | None
    encounter_id: uuid.UUID | None = None


class ObservationCreateRequest(BaseModel):
    status: str = "final"
    code: str | None = None
    code_display: str | None = None
    category: str | None = None
    panel: str | None = None
    effective_date_time: TzDateTime | None = None
    value_quantity: float | None = None
    value_unit: str | None = None
    value_string: str | None = None
    reference_range: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    encounter_id: uuid.UUID | None = None
    component_group_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_vital_range(self):
        """WS-4: reject implausible vitals (422) — labs pass through untouched."""
        check_vital(self.code, self.value_quantity)
        return self
