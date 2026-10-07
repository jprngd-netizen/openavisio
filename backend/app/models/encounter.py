import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class Encounter(OwnedResource):
    __tablename__ = "encounters"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="finished")
    encounter_type: Mapped[str | None] = mapped_column(String(50))
    encounter_date: Mapped[str | None] = mapped_column(String(50))  # ISO-8601 string
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    history: Mapped[str | None] = mapped_column(Text)
    physical_exam: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
    cid10_code: Mapped[str | None] = mapped_column(String(20))
    cid10_display: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="encounters")  # noqa: F821