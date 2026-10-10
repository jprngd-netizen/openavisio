import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, and_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource
from app.services.encounter_seal import content_hash, snapshot_from_encounter

if TYPE_CHECKING:
    from app.models.calendar import CalendarEvent
    from app.models.document import DocumentReference
    from app.models.encounter_condition import EncounterCondition
    from app.models.encounter_version import EncounterVersion
    from app.models.observation import Observation
    from app.models.prescription import Prescriber, Prescription
    from app.models.referral import Referral


class EncounterType(StrEnum):
    """Controlled taxonomy for `encounter_type` (WS-10, DEC-3 approved).

    The column stays a free ``String`` (legacy rows keep their raw value); the
    schema restricts *writes* to these values, plus the small set of legacy
    free-text labels the app already emitted (see ``schemas.encounter``).
    """

    outpatient = "outpatient"
    emergency = "emergency"
    telemedicine = "telemedicine"
    follow_up = "follow_up"
    home_visit = "home_visit"
    other = "other"


class Encounter(OwnedResource):
    __tablename__ = "encounters"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="finished")
    encounter_type: Mapped[str | None] = mapped_column(String(50))
    # WS-5: typed instant (was an ISO-8601 String). The legacy `encounter_date`
    # String column is retained read-only by the DB until a later cleanup
    # migration drops it; the ORM attribute now maps to `encounter_date_ts`.
    encounter_date: Mapped[datetime | None] = mapped_column("encounter_date_ts", DateTime(timezone=True))
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    history: Mapped[str | None] = mapped_column(Text)
    physical_exam: Mapped[str | None] = mapped_column(Text)
    assessment: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
    cid10_code: Mapped[str | None] = mapped_column(String(20))
    cid10_display: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    # WS-6: the professional responsible for this note. Nullable FK to the
    # Prescriber singleton (board_code/number/state live there). The seal keeps
    # its own snapshot of those council fields, so the signed history is
    # self-sufficient even if the Prescriber is edited later.
    prescriber_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescribers.id"), nullable=True, index=True
    )

    prescriber: Mapped["Prescriber | None"] = relationship("Prescriber", lazy="selectin")  # noqa: F821

    patient: Mapped["Patient"] = relationship("Patient", back_populates="encounters")  # noqa: F821
    # Vitals captured in this consultation, stored as Observation rows
    # (category="measurement") linked by encounter_id. View-only: the encounter
    # never owns them; they are written through the encounter router.
    measurements: Mapped[list["Observation"]] = relationship(  # noqa: F821
        "Observation",
        primaryjoin="and_(Encounter.id == Observation.encounter_id, Observation.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="Observation.effective_date_time",
    )
    # WS-3: the diagnoses recorded in this consultation, each linked to a
    # canonical Condition. View-only like the vitals: rows are written through
    # the encounter router, which reconciles the links explicitly.
    diagnoses: Mapped[list["EncounterCondition"]] = relationship(  # noqa: F821
        "EncounterCondition",
        primaryjoin="and_(Encounter.id == EncounterCondition.encounter_id, EncounterCondition.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="EncounterCondition.created_at",
    )
    # WS-6: the immutable seals of this note, oldest first. View-only and
    # append-only: the router inserts versions, nothing here is ever edited.
    versions: Mapped[list["EncounterVersion"]] = relationship(  # noqa: F821
        "EncounterVersion",
        primaryjoin="and_(Encounter.id == EncounterVersion.encounter_id, EncounterVersion.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="EncounterVersion.version",
    )
    # WS-10: follow-up appointments scheduled from this consultation — the
    # CalendarEvent rows (category=appointment) that point back at it. View-only,
    # like the vitals: the calendar router owns those rows.
    follow_ups: Mapped[list["CalendarEvent"]] = relationship(  # noqa: F821
        "CalendarEvent",
        primaryjoin="and_(Encounter.id == CalendarEvent.encounter_id, CalendarEvent.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="CalendarEvent.start_at",
    )
    # WS-10: referrals issued from this consultation. View-only and newest first.
    referrals: Mapped[list["Referral"]] = relationship(  # noqa: F821
        "Referral",
        primaryjoin="and_(Encounter.id == Referral.encounter_id, Referral.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="Referral.created_at",
    )
    # WS-8: prescriptions issued from this consultation. View-only: the
    # prescription router owns those rows; linking goes through the encounter
    # router's /link endpoint, which writes Prescription.encounter_id.
    prescriptions: Mapped[list["Prescription"]] = relationship(  # noqa: F821
        "Prescription",
        primaryjoin="and_(Encounter.id == Prescription.encounter_id, Prescription.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="Prescription.created_at",
    )
    # WS-8: exams (lab reports stored as DocumentReference rows) requested or
    # interpreted in this consultation. View-only: the document vault owns the
    # rows; linking writes DocumentReference.encounter_id.
    exams: Mapped[list["DocumentReference"]] = relationship(  # noqa: F821
        "DocumentReference",
        primaryjoin="and_(Encounter.id == DocumentReference.encounter_id, DocumentReference.is_deleted == False)",  # noqa: E712
        viewonly=True,
        lazy="selectin",
        order_by="DocumentReference.created_at",
    )

    @property
    def prescriber_name(self) -> str | None:
        """Full name of the responsible professional, if one is set."""
        if not self.prescriber:
            return None
        parts = [self.prescriber.given_name, self.prescriber.family_name]
        return " ".join(p for p in parts if p) or None

    @property
    def board_code(self) -> str | None:
        return self.prescriber.board_code if self.prescriber else None

    @property
    def board_number(self) -> str | None:
        return self.prescriber.board_number if self.prescriber else None

    @property
    def board_state(self) -> str | None:
        return self.prescriber.board_state if self.prescriber else None

    @property
    def last_version(self) -> "EncounterVersion | None":
        """The most recent seal, or None if the note has never been signed."""
        return self.versions[-1] if self.versions else None

    @property
    def modified_since_signed(self) -> bool:
        """True when the current content differs from the last sealed content.

        Recomputed from the live note against the stored hash of the last
        version: the seal is never mutated, only compared.
        """
        latest = self.last_version
        if latest is None:
            return False
        return content_hash(snapshot_from_encounter(self)) != latest.content_hash