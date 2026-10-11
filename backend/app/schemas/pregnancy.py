import uuid
from datetime import date, datetime

from pydantic import BaseModel, model_validator

from app.models.pregnancy import PregnancyStatus
from app.schemas.common import OrmBase
from app.services.gestation import display_gestational_age, naegele_due_date


class GestationalAgeDto(OrmBase):
    """Gestational age for one explicit ``as_of`` date (never "today")."""

    weeks: int
    days: int
    total_days: int
    as_of: date
    basis: str  # "lmp" | "ultrasound"


class PregnancyDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    lmp_date: date | None
    estimated_due_date: date | None
    ultrasound_due_date: date | None
    ultrasound_date: date | None
    ended_at: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    # Computed on demand. For an ended episode it is frozen at ``ended_at``;
    # for an active one it reflects the caller-supplied ``as_of`` (the live
    # panel's date). ``None`` when there is no dating basis or ``as_of`` while
    # still active.
    gestational_age: GestationalAgeDto | None = None

    @classmethod
    def from_model(cls, pregnancy, *, as_of: date | None = None) -> "PregnancyDto":
        ga = display_gestational_age(pregnancy, as_of=as_of)
        return cls(
            id=pregnancy.id,
            patient_id=pregnancy.patient_id,
            status=pregnancy.status,
            lmp_date=pregnancy.lmp_date,
            estimated_due_date=pregnancy.estimated_due_date,
            ultrasound_due_date=pregnancy.ultrasound_due_date,
            ultrasound_date=pregnancy.ultrasound_date,
            ended_at=pregnancy.ended_at,
            notes=pregnancy.notes,
            created_at=pregnancy.created_at,
            updated_at=pregnancy.updated_at,
            gestational_age=(
                GestationalAgeDto(
                    weeks=ga.weeks,
                    days=ga.days,
                    total_days=ga.total_days,
                    as_of=ga.as_of,
                    basis=ga.basis,
                )
                if ga is not None
                else None
            ),
        )


class PregnancyCreateRequest(BaseModel):
    status: PregnancyStatus = PregnancyStatus.active
    lmp_date: date | None = None
    estimated_due_date: date | None = None
    ultrasound_due_date: date | None = None
    ultrasound_date: date | None = None
    ended_at: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _default_due_date(self) -> "PregnancyCreateRequest":
        # DPP por Naegele derivada da DUM quando não informada (armazenada).
        if self.estimated_due_date is None and self.lmp_date is not None:
            self.estimated_due_date = naegele_due_date(self.lmp_date)
        return self


class PregnancyUpdateRequest(BaseModel):
    status: PregnancyStatus | None = None
    lmp_date: date | None = None
    estimated_due_date: date | None = None
    ultrasound_due_date: date | None = None
    ultrasound_date: date | None = None
    ended_at: date | None = None
    notes: str | None = None


class ObstetricSummaryDto(OrmBase):
    """Derived GOP (OB-DEC-1): counts computed from the episodes, not stored on
    ``Patient``."""

    gravida: int  # total episodes (G)
    para: int  # episodes reaching delivery (P)
    aborto: int  # pregnancy losses (A)
