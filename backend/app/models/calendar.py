import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource

if TYPE_CHECKING:
    from app.models.encounter import Encounter


class EventCategory(StrEnum):
    appointment = "appointment"
    milestone = "milestone"


class DevelopmentalDomain(StrEnum):
    motor = "motor"
    speech = "speech"
    cognitive = "cognitive"
    social = "social"


class CalendarEvent(OwnedResource):
    __tablename__ = "calendar_events"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Milestone support (issue #11): appointment | milestone; domain only for milestones.
    category: Mapped[str] = mapped_column(String(20), nullable=False, default=EventCategory.appointment, index=True)
    developmental_domain: Mapped[str | None] = mapped_column(String(20))
    start_at: Mapped[datetime] = mapped_column("start_at_ts", DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column("end_at_ts", DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    provider: Mapped[str | None] = mapped_column(String(256))
    location: Mapped[str | None] = mapped_column(String(512))
    purpose: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    document_reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("document_references.id"), nullable=True)
    # WS-10: when this event is a follow-up scheduled from a consultation, the
    # encounter it belongs to. Nullable — most events are manual.
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=True, index=True
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped["Patient"] = relationship("Patient", back_populates="calendar_events")  # noqa: F821
