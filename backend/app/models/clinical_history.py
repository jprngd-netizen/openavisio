import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ClinicalHistory(BaseModel):
    """Longitudinal clinical history (anamnesis) — 1:1 with the patient.

    Personal/family/surgical history, allergies and habits are free text. The
    derived antecedents (diagnoses/medications) are NOT stored here — they are
    the canonical `conditions`/`medications` resources, edited in place.
    """

    __tablename__ = "clinical_histories"
    __table_args__ = (UniqueConstraint("patient_id", name="uq_clinical_histories_patient"),)

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    personal_history: Mapped[str | None] = mapped_column(Text)
    family_history: Mapped[str | None] = mapped_column(Text)
    surgical_history: Mapped[str | None] = mapped_column(Text)
    allergies: Mapped[str | None] = mapped_column(Text)
    habits: Mapped[str | None] = mapped_column(Text)
