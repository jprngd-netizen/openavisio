import uuid
from datetime import date as _date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class ReferralStatus(StrEnum):
    """Lifecycle of a referral to another speciality (FHIR ``ServiceRequest``-like)."""

    draft = "draft"
    sent = "sent"
    completed = "completed"
    cancelled = "cancelled"


class Referral(OwnedResource):
    """A referral (encaminhamento) issued from a consultation (WS-10).

    Records where the patient was sent (*target_specialty*), why (*reason*) and
    the tracking status, so a consultation's outcome (continuity of care) is a
    first-class record instead of prose in the note. *encounter_id* links it back
    to the consultation it came from (nullable: a referral may stand alone).
    """

    __tablename__ = "referrals"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=True, index=True
    )
    target_specialty: Mapped[str] = mapped_column(String(256), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=ReferralStatus.draft)
    # WS-5 typed pure date (day the referral was issued / dated), nullable.
    date: Mapped[_date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
