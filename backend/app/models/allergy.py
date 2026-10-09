import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class AllergySeverity(StrEnum):
    """Controlled severity of an allergic reaction (FHIR severity)."""

    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    life_threatening = "life_threatening"


class AllergyCriticality(StrEnum):
    """Clinical criticality of the allergy/intolerance (FHIR criticality)."""

    low = "low"
    high = "high"
    unable_to_assess = "unable_to_assess"


class AllergyClinicalStatus(StrEnum):
    """Lifecycle status of the allergy record (FHIR clinicalStatus)."""

    active = "active"
    inactive = "inactive"
    resolved = "resolved"


class Allergy(OwnedResource):
    """Structured allergy / intolerance — FHIR ``AllergyIntolerance``-like (WS-1).

    Replaces the narrative ``ClinicalHistory.allergies`` free text, which is kept
    as a non-used legacy column (dropped in a later cleanup). The controlled
    values are ``StrEnum`` members so no free ``String`` ever reaches the DB.
    """

    __tablename__ = "allergies"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    substance_code: Mapped[str | None] = mapped_column(String(100))
    substance_display: Mapped[str] = mapped_column(String(256), nullable=False)
    reaction: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(30))
    # WS-5 typed onset instant (timezone-aware); nullable — often unknown.
    onset: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criticality: Mapped[str] = mapped_column(String(30), default=AllergyCriticality.unable_to_assess)
    clinical_status: Mapped[str] = mapped_column(String(30), default=AllergyClinicalStatus.active)
    note: Mapped[str | None] = mapped_column(Text)
