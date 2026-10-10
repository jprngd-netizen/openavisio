"""Safety-summary DTOs (WS-9) — the lean clinical banner on the chart cover.

One aggregated read: only the *active* allergies, the currently-effective
medications and the *active* problems, each reduced to the few fields the cover
banner renders. Deliberately slimmer than the full CRUD DTOs so the banner is a
single cheap call and nothing else is dragged in.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.common import OrmBase, TzDateTime


class SafetyAllergyDto(OrmBase):
    id: uuid.UUID
    substance_display: str
    reaction: str | None
    severity: str | None
    criticality: str
    clinical_status: str


class SafetyMedicationDto(OrmBase):
    id: uuid.UUID
    medication_display: str
    dosage_text: str | None
    status: str
    effective_start: TzDateTime | None
    effective_end: TzDateTime | None


class SafetyConditionDto(OrmBase):
    id: uuid.UUID
    code: str | None
    code_display: str
    severity: str | None
    clinical_status: str


class SafetySummaryDto(BaseModel):
    """Active allergies, active medications and active problems in one call."""

    allergies: list[SafetyAllergyDto]
    medications: list[SafetyMedicationDto]
    conditions: list[SafetyConditionDto]
