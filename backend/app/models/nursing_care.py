import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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


class NursingCareSubcategory(StrEnum):
    """Finer nursing-care subcategory (FExEO-SUS / CEEO-Rede Alyne, R4 Fase 1).

    A controlled ``StrEnum`` distinguishing the four acompanhamento instruments
    that are charted as nursing care: ``labor`` (I.2 — trabalho de parto, parto,
    nascimento e pós-parto imediato), ``postpartum`` (I.3 — pós-parto e
    alojamento conjunto), ``sexual_reproductive`` (I.4 — saúde sexual e
    reprodutiva) and ``general`` (any other nursing note). Nullable: a record
    charted before this vocabulary existed, or one that does not fit an
    instrument, simply carries no subcategory.
    """

    labor = "labor"
    postpartum = "postpartum"
    sexual_reproductive = "sexual_reproductive"
    general = "general"


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

    # --- FExEO-SUS structured fields (R4 Fase 1, itens 3 e 4). All
    # nullable/additive so existing records and data are never broken. ---
    # Subcategoria do cuidado de enfermagem (labor/postpartum/
    # sexual_reproductive/general) — diferencia os 4 instrumentos de I.2–I.4.
    subcategory: Mapped[str | None] = mapped_column(String(30))
    # Tipo de instrumento de acompanhamento aplicado (proveniência do registro).
    instrument_type: Mapped[str | None] = mapped_column(String(120))
    # Dados estruturados específicos do instrumento — JSON (JSONB).
    structured_data: Mapped[dict | None] = mapped_column(JSONB)
