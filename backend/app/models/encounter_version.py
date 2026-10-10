import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.encounter import Encounter


class EncounterVersion(BaseModel):
    """An immutable, signed version (seal) of an ``Encounter`` note (WS-6).

    APPEND-ONLY: a row is written once and never updated or deleted. Editing the
    consultation does *not* touch its versions; signing again appends
    ``version + 1`` with a fresh hash. The row is self-sufficient — it carries
    the professional's council snapshot (``board_*`` + ``professional_name``) as
    it stood at seal time, so a later edit to the ``Prescriber`` cannot rewrite
    the signed history.

    ``content`` is the JSON snapshot of the note (fields + diagnoses) at seal
    time; ``content_hash`` is the deterministic SHA-256 of its canonical form
    (see ``app.services.encounter_seal``), so any holder of ``content`` can
    recompute and verify the digest.
    """

    __tablename__ = "encounter_versions"
    __table_args__ = (UniqueConstraint("encounter_id", "version", name="uq_encounter_versions_encounter_version"),)

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Professional snapshot at seal time (self-sufficient version).
    professional_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    board_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    board_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    board_state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    encounter: Mapped["Encounter"] = relationship("Encounter", viewonly=True)  # noqa: F821
