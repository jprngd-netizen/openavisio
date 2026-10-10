import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class ImmunizationStatus(StrEnum):
    """Lifecycle status of an immunization record (FHIR ``Immunization.status``)."""

    completed = "completed"
    entered_in_error = "entered_in_error"
    not_done = "not_done"


class Immunization(OwnedResource):
    """Structured immunization (vaccine) record — FHIR ``Immunization``-like (WS-7).

    Replaces the loose "vaccines" narrative: a vaccine, its dose number,
    occurrence date, lot and administration details are first-class fields. The
    controlled status is a ``StrEnum`` so no free ``String`` value reaches the DB.
    """

    __tablename__ = "immunizations"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    vaccine_code: Mapped[str | None] = mapped_column(String(100))
    vaccine_display: Mapped[str] = mapped_column(String(256), nullable=False)
    dose_number: Mapped[int | None] = mapped_column()
    # WS-5 typed pure date (day of occurrence) — nullable, often only the year is known.
    occurrence_date: Mapped[date | None] = mapped_column(Date)
    lot_number: Mapped[str | None] = mapped_column(String(100))
    route: Mapped[str | None] = mapped_column(String(100))
    site: Mapped[str | None] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(256))
    reaction: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=ImmunizationStatus.completed)
    note: Mapped[str | None] = mapped_column(Text)
