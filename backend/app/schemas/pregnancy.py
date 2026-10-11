import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.pregnancy import (
    EdemaSeverity,
    FetalPresentation,
    PregnancyStatus,
    Proteinuria,
)
from app.schemas.common import OrmBase
from app.services.gestation import (
    display_gestational_age,
    gestational_age,
    naegele_due_date,
)


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
    # Number of prenatal visits recorded against this episode (OB-2).
    visit_count: int = 0

    @classmethod
    def from_model(
        cls, pregnancy, *, as_of: date | None = None, visit_count: int = 0
    ) -> "PregnancyDto":
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
            visit_count=visit_count,
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


class PregnancyVisitDto(OrmBase):
    """A prenatal visit (OB-2). ``gestational_age`` is computed for the visit's
    own date (``as_of=visit_date``) — the record is a snapshot of its date."""

    id: uuid.UUID
    pregnancy_id: uuid.UUID
    visit_date: date
    fundal_height_cm: float | None
    fetal_heart_rate_bpm: int | None
    presentation: str | None
    edema: str | None
    proteinuria: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    gestational_age: GestationalAgeDto | None = None

    @classmethod
    def from_model(cls, visit, *, pregnancy) -> "PregnancyVisitDto":
        # GA on the visit's own date, using the episode's dating basis (DUM or
        # the ultrasound-corrected DPP). Never "today".
        ga = gestational_age(
            visit.visit_date,
            lmp_date=pregnancy.lmp_date,
            ultrasound_due_date=pregnancy.ultrasound_due_date,
        )
        return cls(
            id=visit.id,
            pregnancy_id=visit.pregnancy_id,
            visit_date=visit.visit_date,
            fundal_height_cm=(
                float(visit.fundal_height_cm) if visit.fundal_height_cm is not None else None
            ),
            fetal_heart_rate_bpm=visit.fetal_heart_rate_bpm,
            presentation=visit.presentation,
            edema=visit.edema,
            proteinuria=visit.proteinuria,
            notes=visit.notes,
            created_at=visit.created_at,
            updated_at=visit.updated_at,
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


class PregnancyVisitCreateRequest(BaseModel):
    visit_date: date
    # Plausible obstetric ranges: fundal height only ever measured > 0 and
    # well under 100 cm; the fetal heart rate lives in the 50–250 bpm window.
    fundal_height_cm: float | None = Field(default=None, gt=0, lt=100)
    fetal_heart_rate_bpm: int | None = Field(default=None, ge=50, le=250)
    presentation: FetalPresentation | None = None
    edema: EdemaSeverity | None = None
    proteinuria: Proteinuria | None = None
    notes: str | None = None


class PregnancyVisitUpdateRequest(BaseModel):
    visit_date: date | None = None
    fundal_height_cm: float | None = Field(default=None, gt=0, lt=100)
    fetal_heart_rate_bpm: int | None = Field(default=None, ge=50, le=250)
    presentation: FetalPresentation | None = None
    edema: EdemaSeverity | None = None
    proteinuria: Proteinuria | None = None
    notes: str | None = None
