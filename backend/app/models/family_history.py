import uuid
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class FamilyRelationship(StrEnum):
    """Controlled family relationship (degree/kinship) of a family-history entry."""

    mother = "mother"
    father = "father"
    brother = "brother"
    sister = "sister"
    son = "son"
    daughter = "daughter"
    grandparent = "grandparent"
    other = "other"


class FamilyHistory(OwnedResource):
    """Structured family history — one entry per relative/condition (WS-7).

    Replaces the free-text ``ClinicalHistory.family_history`` narrative with a
    resource keyed on the degree of kinship. The legacy column is deliberately
    kept (non-used legacy) — dropping it is a later cleanup stage.
    """

    __tablename__ = "family_history"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    condition_code: Mapped[str | None] = mapped_column(String(100))
    condition_display: Mapped[str] = mapped_column(String(256), nullable=False)
    age_at_onset: Mapped[int | None] = mapped_column()
    deceased: Mapped[bool | None] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)
