import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.newborn_record import NewbornClassification, NewbornRecordSex
from app.schemas.common import OrmBase, TzDateTime


class NewbornRecordDto(OrmBase):
    """A live newborn's structured record, as read back (FExEO-SUS I.2/I.3).

    ``birth_datetime`` is the instant the newborn was born — the record is a
    snapshot of that date, never of "today". Every clinical field is optional.
    """

    id: uuid.UUID
    pregnancy_outcome_id: uuid.UUID
    birth_datetime: TzDateTime | None = None
    sex: str | None = None
    delivery_type: str | None = None
    gestational_age_weeks: float | None = None
    classification: str | None = None
    apgar_1: int | None = None
    apgar_5: int | None = None
    apgar_10: int | None = None
    weight_g: int | None = None
    length_cm: float | None = None
    pc_cm: float | None = None
    pt_cm: float | None = None
    pa_cm: float | None = None
    physical_exam: dict | None = None
    reflexes: dict | None = None
    feeding: str | None = None
    eliminations: dict | None = None
    hypoglycemia: bool | None = None
    hypothermia: bool | None = None
    immunization: dict | None = None
    congenital_malformation: bool | str | None = None
    reanimation: dict | None = None
    skin_to_skin_1h: bool | None = None
    cord_clamping: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class NewbornRecordCreateRequest(BaseModel):
    """Create the newborn record of a closed episode (FExEO-SUS I.2/I.3).

    Every field is optional: the record may be opened with only the outcome link
    and filled in progressively. Plausible ranges guard data entry (Apgar 0–10,
    weight under 8 kg, anthropometry under 100 cm).
    """

    birth_datetime: TzDateTime | None = None
    sex: NewbornRecordSex | None = None
    delivery_type: str | None = None
    gestational_age_weeks: float | None = Field(default=None, ge=0, le=50)
    classification: NewbornClassification | None = None
    apgar_1: int | None = Field(default=None, ge=0, le=10)
    apgar_5: int | None = Field(default=None, ge=0, le=10)
    apgar_10: int | None = Field(default=None, ge=0, le=10)
    weight_g: int | None = Field(default=None, gt=0, le=8000)
    length_cm: float | None = Field(default=None, gt=0, lt=100)
    pc_cm: float | None = Field(default=None, gt=0, lt=100)
    pt_cm: float | None = Field(default=None, gt=0, lt=100)
    pa_cm: float | None = Field(default=None, gt=0, lt=100)
    physical_exam: dict | None = None
    reflexes: dict | None = None
    feeding: str | None = None
    eliminations: dict | None = None
    hypoglycemia: bool | None = None
    hypothermia: bool | None = None
    immunization: dict | None = None
    congenital_malformation: bool | str | None = None
    reanimation: dict | None = None
    skin_to_skin_1h: bool | None = None
    cord_clamping: str | None = None
    notes: str | None = None


class NewbornRecordUpdateRequest(BaseModel):
    """Partial update of a newborn record. Every field is optional."""

    birth_datetime: TzDateTime | None = None
    sex: NewbornRecordSex | None = None
    delivery_type: str | None = None
    gestational_age_weeks: float | None = Field(default=None, ge=0, le=50)
    classification: NewbornClassification | None = None
    apgar_1: int | None = Field(default=None, ge=0, le=10)
    apgar_5: int | None = Field(default=None, ge=0, le=10)
    apgar_10: int | None = Field(default=None, ge=0, le=10)
    weight_g: int | None = Field(default=None, gt=0, le=8000)
    length_cm: float | None = Field(default=None, gt=0, lt=100)
    pc_cm: float | None = Field(default=None, gt=0, lt=100)
    pt_cm: float | None = Field(default=None, gt=0, lt=100)
    pa_cm: float | None = Field(default=None, gt=0, lt=100)
    physical_exam: dict | None = None
    reflexes: dict | None = None
    feeding: str | None = None
    eliminations: dict | None = None
    hypoglycemia: bool | None = None
    hypothermia: bool | None = None
    immunization: dict | None = None
    congenital_malformation: bool | str | None = None
    reanimation: dict | None = None
    skin_to_skin_1h: bool | None = None
    cord_clamping: str | None = None
    notes: str | None = None
