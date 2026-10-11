import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class NursingCareCategory(StrEnum):
    """Whether a nursing record is a general note or an obstetric one (OB-5).

    A controlled ``StrEnum`` so no free ``String`` reaches the DB. A record may
    belong to the obstetric context (and then optionally cite the gestation it
    annotates) or to the patient's general care — the two are the same resource
    under two categories, per the approved scope (general + obstetric).
    """

    general = "general"
    obstetric = "obstetric"


class NursingCare(OwnedResource):
    """A dated, frozen nursing-care record (OB-5).

    Nursing documentation is *dated*: ``occurred_at`` is the instant the care
    happened, and it is the one date the record is anchored to. Following the
    plan's principle **"the record is a snapshot of its date"**, nothing on the
    record is derived for "today" — the record stores what was true at
    ``occurred_at`` and is never rewritten by a later value. ``occurred_at`` is a
    typed ``DateTime(timezone=True)`` (WS-5), not a string.

    ``category`` splits the approved scope: ``general`` (any nursing note) and
    ``obstetric`` (a note in the obstetric context). When obstetric, the record
    *may* be linked to the episode it annotates via the nullable ``pregnancy_id``
    — the router enforces that the gestation belongs to the SAME patient (422).
    The Gestation section deliberately does **not** duplicate prenatal
    measurements: it records only what has no home elsewhere.

    The free-text ``notes`` is the nursing narrative (the "cuidado"); it follows
    the repo convention for a clinical record's free text (``Pregnancy.notes``,
    ``PregnancyVisit.notes``, ``PregnancyOutcome.notes``). ``performed_by`` names
    the professional who carried out the care (nullable — often charted later).
    Soft-deleted via ``is_deleted``; ``occurred_at`` is indexed because the
    listing is always newest-first.
    """

    __tablename__ = "nursing_care"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    # The instant the care occurred — the record's anchor and its only date.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(20), default=NursingCareCategory.general, nullable=False
    )
    # Optional link to the gestation this obstetric record annotates.
    pregnancy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pregnancies.id"), nullable=True, index=True
    )
    # The nursing narrative (the record itself).
    notes: Mapped[str | None] = mapped_column(Text)
    # Who carried out the care (free text; nullable).
    performed_by: Mapped[str | None] = mapped_column(String(256))
