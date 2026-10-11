import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Observation(OwnedResource):
    __tablename__ = "observations"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="final")
    code: Mapped[str | None] = mapped_column(String(100))
    code_display: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(100))
    panel: Mapped[str | None] = mapped_column(String(128))  # #69: report section, e.g. "Blutbild"
    # WS-4: blood pressure is one panel made of two components (systolic +
    # diastolic taken at the same instant). The two Observation rows carry the
    # same component_group_id so they read back (and chart) as one measurement.
    # Distinct from `panel`, which is the lab report section.
    component_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # WS-5: typed instant (legacy ISO-8601 String column kept until cleanup).
    effective_date_time: Mapped[datetime | None] = mapped_column("effective_date_time_ts", DateTime(timezone=True))
    value_quantity: Mapped[float | None] = mapped_column(Float)
    value_unit: Mapped[str | None] = mapped_column(String(50))
    value_string: Mapped[str | None] = mapped_column(Text)
    reference_range: Mapped[str | None] = mapped_column(String(100))  # #69: raw printed range
    ref_low: Mapped[float | None] = mapped_column(Float)
    ref_high: Mapped[float | None] = mapped_column(Float)
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)
    # Vitals recorded during a consultation point back at that encounter, so the
    # measurements history and the encounter record stay one single source of truth.
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=True, index=True)
    # OB-4: a vital (weight, blood pressure) measured during a gestation points
    # back at the episode, so prenatal monitoring reads the same Observation rows
    # instead of duplicating PA/weight into PregnancyVisit.
    pregnancy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pregnancies.id"), nullable=True, index=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="observations")  # noqa: F821
