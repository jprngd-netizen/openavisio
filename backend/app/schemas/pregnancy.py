import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.pregnancy import (
    LIVE_BIRTH_OUTCOMES,
    EdemaSeverity,
    FetalPresentation,
    NewbornSex,
    PregnancyOutcomeType,
    PregnancyStatus,
    Proteinuria,
)
from app.schemas.common import OrmBase
from app.schemas.encounter import LinkedExamDto
from app.schemas.observation import ObservationDto
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


class PregnancyOutcomeDto(OrmBase):
    """The dated outcome that closes an episode (OB-3).

    ``gestational_age`` is computed for the outcome's own date
    (``as_of=outcome_date``) — the record is a snapshot of its date.
    """

    id: uuid.UUID
    pregnancy_id: uuid.UUID
    outcome_type: str
    outcome_date: date
    newborn_weight_g: int | None
    apgar_1: int | None
    apgar_5: int | None
    newborn_sex: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    gestational_age: GestationalAgeDto | None = None

    @classmethod
    def from_model(cls, outcome, *, pregnancy) -> "PregnancyOutcomeDto":
        # GA at the outcome date, using the episode's dating basis (DUM or the
        # ultrasound-corrected DPP). Never "today".
        ga = gestational_age(
            outcome.outcome_date,
            lmp_date=pregnancy.lmp_date,
            ultrasound_due_date=pregnancy.ultrasound_due_date,
        )
        return cls(
            id=outcome.id,
            pregnancy_id=outcome.pregnancy_id,
            outcome_type=outcome.outcome_type,
            outcome_date=outcome.outcome_date,
            newborn_weight_g=outcome.newborn_weight_g,
            apgar_1=outcome.apgar_1,
            apgar_5=outcome.apgar_5,
            newborn_sex=outcome.newborn_sex,
            notes=outcome.notes,
            created_at=outcome.created_at,
            updated_at=outcome.updated_at,
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


class PregnancyConditionDto(OrmBase):
    """An intercorrência linked to an episode, as read back (OB-4).

    The linked problem-list ``Condition`` plus the CID-10 snapshot as it read
    when it was recorded — mirrors ``EncounterDiagnosisDto`` (WS-3).
    """

    condition_id: uuid.UUID
    cid10_code: str | None
    cid10_display: str | None

    @classmethod
    def from_model(cls, link) -> "PregnancyConditionDto":
        return cls(
            condition_id=link.condition_id,
            cid10_code=link.cid10_code,
            cid10_display=link.cid10_display,
        )


class PregnancyConditionInput(BaseModel):
    """Register an intercorrência in a gestation (OB-4).

    ``cid10_code``/``cid10_display`` are the CID-10 snapshot as picked in the
    editor; ``condition_id`` optionally pins the intercorrência to an existing
    problem-list Condition instead of resolving one by code. When omitted, the
    router finds-or-creates the patient's Condition by (patient_id, code) reusing
    the WS-3 service — so the same diagnosis never duplicates in the problem list.
    """

    cid10_code: str | None = None
    cid10_display: str | None = None
    condition_id: uuid.UUID | None = None


class PregnancyLinkRequest(BaseModel):
    """Link (or unlink) one resource to an episode (OB-4).

    Exactly one of ``observation_id`` (a vital, category=measurement) or
    ``document_id`` (an exam / lab report) must be set; the other stays null. The
    resource must belong to the same patient as the gestation (422 otherwise).
    """

    observation_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "PregnancyLinkRequest":
        if (self.observation_id is None) == (self.document_id is None):
            raise ValueError("set exactly one of observation_id or document_id")
        return self


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
    # The outcome that closed the episode, when one was recorded (OB-3).
    outcome: PregnancyOutcomeDto | None = None
    # OB-4 clinical integrations: intercorrências (linked Conditions), linked
    # vitals (Observations) and linked exams (DocumentReferences), with counts.
    condition_count: int = 0
    vital_count: int = 0
    exam_count: int = 0
    conditions: list[PregnancyConditionDto] = []
    vitals: list[ObservationDto] = []
    exams: list[LinkedExamDto] = []

    @classmethod
    def from_model(
        cls,
        pregnancy,
        *,
        as_of: date | None = None,
        visit_count: int = 0,
        outcome=None,
        conditions: list[PregnancyConditionDto] | None = None,
        vitals: list[ObservationDto] | None = None,
        exams: list[LinkedExamDto] | None = None,
    ) -> "PregnancyDto":
        conditions = conditions or []
        vitals = vitals or []
        exams = exams or []
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
            outcome=(
                PregnancyOutcomeDto.from_model(outcome, pregnancy=pregnancy)
                if outcome is not None
                else None
            ),
            condition_count=len(conditions),
            vital_count=len(vitals),
            exam_count=len(exams),
            conditions=conditions,
            vitals=vitals,
            exams=exams,
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


class PregnancyOutcomeCreateRequest(BaseModel):
    """Register the outcome that closes an episode (OB-3).

    Newborn fields are only accepted for a live birth (vaginal/cesarean
    delivery); for a loss they must be omitted — a 422 otherwise, so a loss can
    never carry a spurious newborn record.
    """

    outcome_type: PregnancyOutcomeType
    outcome_date: date
    # Newborn data — live birth only. Plausible ranges guard data entry.
    newborn_weight_g: int | None = Field(default=None, gt=0, le=8000)
    apgar_1: int | None = Field(default=None, ge=0, le=10)
    apgar_5: int | None = Field(default=None, ge=0, le=10)
    newborn_sex: NewbornSex | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _newborn_only_for_live_birth(self) -> "PregnancyOutcomeCreateRequest":
        if self.outcome_type not in LIVE_BIRTH_OUTCOMES and any(
            v is not None
            for v in (self.newborn_weight_g, self.apgar_1, self.apgar_5, self.newborn_sex)
        ):
            raise ValueError(
                "newborn data is only valid for a live birth "
                "(vaginal or cesarean delivery)"
            )
        return self


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
