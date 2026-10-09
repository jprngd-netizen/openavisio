import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.condition import Condition
    from app.models.encounter import Encounter


class EncounterCondition(BaseModel):
    """A diagnosis recorded in a consultation, linked to its canonical Condition (WS-3).

    Mirrors ``ConditionSource``: the encounter cites the problem-list entry the
    diagnosis belongs to, so a consultation can carry N diagnoses and each one
    shows where it came from. The CID-10 snapshot is kept as it read at that
    visit, so renaming the Condition later does not rewrite history. Removing a
    diagnosis from a consultation soft-deletes only this link — the Condition
    (the problem list) is never deleted.
    """

    __tablename__ = "encounter_conditions"
    __table_args__ = (UniqueConstraint("encounter_id", "condition_id"),)

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False, index=True
    )
    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=False, index=True
    )
    cid10_code: Mapped[str | None] = mapped_column(String(20))
    cid10_display: Mapped[str | None] = mapped_column(String(256))

    condition: Mapped["Condition"] = relationship("Condition", viewonly=True)  # noqa: F821
    encounter: Mapped["Encounter"] = relationship("Encounter", viewonly=True)  # noqa: F821

    # read by ConditionEncounterSourceDto via from_attributes; needs `encounter` eager-loaded
    @property
    def encounter_date(self) -> datetime | None:
        return self.encounter.encounter_date if self.encounter else None
