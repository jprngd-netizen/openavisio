import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource


class MedicationStatement(OwnedResource):
    __tablename__ = "medication_statements"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    medication_code: Mapped[str | None] = mapped_column(String(100))
    medication_display: Mapped[str] = mapped_column(String(256), nullable=False)
    # WS-5: typed instants (legacy ISO-8601 String columns kept until cleanup).
    date_asserted: Mapped[datetime | None] = mapped_column("date_asserted_ts", DateTime(timezone=True))
    effective_start: Mapped[datetime | None] = mapped_column("effective_start_ts", DateTime(timezone=True))
    effective_end: Mapped[datetime | None] = mapped_column("effective_end_ts", DateTime(timezone=True))
    dosage_text: Mapped[str | None] = mapped_column(String(512))
    dose_quantity: Mapped[float | None] = mapped_column(Float)
    dose_unit: Mapped[str | None] = mapped_column(String(50))
    route: Mapped[str | None] = mapped_column(String(100))
    reason_code: Mapped[str | None] = mapped_column(String(256))
    note: Mapped[str | None] = mapped_column(Text)
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="medications")  # noqa: F821
