import uuid
from datetime import date, datetime

from pydantic import BaseModel, field_validator, model_validator

from app.models.encounter import EncounterType
from app.schemas.calendar import CalendarEventDto
from app.schemas.common import OrmBase, TzDateTime
from app.schemas.observation import ObservationDto
from app.schemas.referral import ReferralDto
from app.services.vital_ranges import check_vital

# WS-10 (DEC-3): the controlled taxonomy is the write contract, but the app
# historically emitted free-text labels into the same column. Those legacy
# values are accepted verbatim so existing clients/rows keep working.
_TAXONOMY = {t.value for t in EncounterType}
_LEGACY_ENCOUNTER_TYPES = {
    "consulta",
    "retorno",
    "teleconsulta",
    "urgencia",
    "urgência",
    "evolucao",
    "evolução",
    "procedimento",
}


def validate_encounter_type(value: str | None) -> str | None:
    """Restrict ``encounter_type`` writes to the taxonomy (plus legacy labels)."""
    if value is None:
        return None
    if value in _TAXONOMY or value.lower() in _LEGACY_ENCOUNTER_TYPES:
        return value
    raise ValueError(
        "encounter_type must be one of: " + ", ".join(sorted(_TAXONOMY))
    )


class EncounterMeasurement(BaseModel):
    """A vital sign captured during the consultation (weight, BP, SpO2, ...).

    WS-4: systolic and diastolic readings taken at the same instant share a
    ``component_group_id`` so they read back as one blood-pressure panel.
    """

    code: str
    code_display: str | None = None
    value_quantity: float | None = None
    value_unit: str | None = None
    component_group_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validate_vital_range(self):
        """Reject implausible vitals with a clear 422 before persisting."""
        check_vital(self.code, self.value_quantity)
        return self


class DiagnosisInput(BaseModel):
    """A diagnosis registered in a consultation (WS-3).

    ``cid10_code``/``cid10_display`` are the CID-10 snapshot as picked in the
    editor; ``condition_id`` optionally pins the diagnosis to an existing
    problem-list Condition instead of resolving one by code. When omitted, the
    router finds-or-creates the Condition by (patient, code).
    """

    cid10_code: str | None = None
    cid10_display: str | None = None
    condition_id: uuid.UUID | None = None


class EncounterDiagnosisDto(OrmBase):
    """A diagnosis as read back: the linked Condition plus the CID-10 snapshot."""

    condition_id: uuid.UUID
    cid10_code: str | None
    cid10_display: str | None


class EncounterVersionSummaryDto(OrmBase):
    """The immutable seal of a consultation note (WS-6), as read back.

    Carries the version number, the moment it was signed and the content hash,
    plus the seeded council snapshot so the responsible professional of that
    signed version is self-sufficient.
    """

    version: int
    content_hash: str
    signed_at: TzDateTime
    signed_by: uuid.UUID
    professional_name: str | None = None
    board_code: str | None = None
    board_number: str | None = None
    board_state: str | None = None


class LinkedPrescriptionDto(OrmBase):
    """A prescription linked to a consultation (WS-8), as read back.

    A lightweight summary on purpose: the full PrescriptionDto pulls in items
    and the archived document, which the prescription's own endpoints own. Here
    the consultation only needs to name what was prescribed.
    """

    id: uuid.UUID
    status: str
    version: int
    issued_at: datetime | None = None
    notes: str | None = None
    signature_state: str | None = None
    created_at: datetime


class LinkedExamDto(OrmBase):
    """A lab report (DocumentReference) linked to a consultation (WS-8).

    The exam unit is the *document* (the report file), not each analyte: a
    panel's individual values are Observation rows hanging off this document.
    """

    id: uuid.UUID
    type: str | None = None
    description: str | None = None
    file_name: str | None = None
    issued_date: date | None = None
    processing_status: str
    verification_status: str
    created_at: datetime


class EncounterDto(OrmBase):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    encounter_type: str | None
    encounter_date: TzDateTime | None
    chief_complaint: str | None
    history: str | None
    physical_exam: str | None
    assessment: str | None
    plan: str | None
    cid10_code: str | None
    cid10_display: str | None
    notes: str | None
    # WS-6: responsible professional + council (rendered from the Prescriber FK).
    prescriber_id: uuid.UUID | None = None
    prescriber_name: str | None = None
    board_code: str | None = None
    board_number: str | None = None
    board_state: str | None = None
    # WS-6: latest seal, and whether the note changed since that seal.
    last_version: EncounterVersionSummaryDto | None = None
    modified_since_signed: bool = False
    measurements: list[ObservationDto] = []
    diagnoses: list[EncounterDiagnosisDto] = []
    # WS-10: continuity of care — return appointments scheduled from this note
    # and referrals issued from it.
    follow_ups: list[CalendarEventDto] = []
    referrals: list[ReferralDto] = []
    # WS-8: what was prescribed and which exams were linked in this attendance.
    prescriptions: list[LinkedPrescriptionDto] = []
    exams: list[LinkedExamDto] = []
    created_at: datetime
    updated_at: datetime


class EncounterLinkRequest(BaseModel):
    """Link (or unlink) one resource to a consultation (WS-8).

    Exactly one of ``prescription_id`` / ``document_id`` must be set; the other
    stays null. The resource must belong to the same patient as the encounter
    (422 otherwise).
    """

    prescription_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.prescription_id is None) == (self.document_id is None):
            raise ValueError("set exactly one of prescription_id or document_id")
        return self


class FollowUpCreateRequest(BaseModel):
    """Schedule a return appointment from a consultation (WS-10)."""

    start_at: TzDateTime
    end_at: TzDateTime | None = None
    title: str | None = None
    purpose: str | None = None


class EncounterCreateRequest(BaseModel):
    status: str = "finished"
    encounter_type: str | None = None
    encounter_date: TzDateTime | None = None
    chief_complaint: str | None = None
    history: str | None = None
    physical_exam: str | None = None
    assessment: str | None = None
    plan: str | None = None
    # deprecated: the single-CID fields are kept for API compatibility; new
    # clients send `diagnoses` and the legacy columns are left NULL.
    cid10_code: str | None = None
    cid10_display: str | None = None
    notes: str | None = None
    # WS-6: responsible professional; defaults to the Prescriber singleton when
    # omitted, so a single-practitioner install attributes notes automatically.
    prescriber_id: uuid.UUID | None = None
    measurements: list[EncounterMeasurement] = []
    diagnoses: list[DiagnosisInput] = []

    _check_type = field_validator("encounter_type")(validate_encounter_type)


class EncounterUpdateRequest(BaseModel):
    status: str | None = None
    encounter_type: str | None = None
    encounter_date: TzDateTime | None = None
    chief_complaint: str | None = None
    history: str | None = None
    physical_exam: str | None = None
    assessment: str | None = None
    plan: str | None = None
    cid10_code: str | None = None
    cid10_display: str | None = None
    notes: str | None = None
    prescriber_id: uuid.UUID | None = None
    measurements: list[EncounterMeasurement] | None = None
    diagnoses: list[DiagnosisInput] | None = None

    _check_type = field_validator("encounter_type")(validate_encounter_type)
