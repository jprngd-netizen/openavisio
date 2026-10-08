import uuid

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ClinicalHistory(BaseModel):
    """Longitudinal anamnesis of the occupational record (section #2 — "História
    Clínica e Ocupacional"). 1:1 with the patient.

    Personal/family/surgical history, allergies and habits are free text.
    Previous employments and risk-agent exposures are kept as JSONB **lists** —
    the minimal shape that renders the section; promote them to their own tables
    if they ever need to be queried or reported per agent.
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
    previous_employments: Mapped[list | None] = mapped_column(JSONB, default=list)
    exposures: Mapped[list | None] = mapped_column(JSONB, default=list)
