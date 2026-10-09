import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, and_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import OwnedResource

if TYPE_CHECKING:
    from app.models.encounter_condition import EncounterCondition
    from app.models.observation import Observation


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