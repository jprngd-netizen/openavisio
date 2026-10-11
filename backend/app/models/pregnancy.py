import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import OwnedResource


class PregnancyStatus(StrEnum):
    """Lifecycle status of a pregnancy episode (OB-1, OB-DEC-3).

    This is the *episode* status — whether the gestation is ongoing and, when
    it ended, the terminal state. The full structured outcome (delivery type,
    newborn data, dates, intercorrências) is OB-3 and lives in its own record;
    ``status`` only classifies the episode envelope. The vocabulary already
    covers the complete outcome taxonomy approved in OB-DEC-3 so the episode
    never needs a lossy "completed/miscarriage" collapse.
    """

    active = "active"
    completed = "completed"
    miscarriage = "miscarriage"
    terminated = "terminated"
    ectopic = "ectopic"
    fetal_death = "fetal_death"


class Pregnancy(OwnedResource):
    """Obstetric episode (gestation) — the resource OB-1 introduces.

    One row per pregnancy. It anchors the prenatal visits (``PregnancyVisit``,
    OB-2) and the outcome (OB-3), which is why it is a real resource and not a
    flag on ``Patient`` (**OB-DEC-1**: GOP is *derived* from these episodes, no
    ``gravida``/``para`` columns on ``Patient``).

    Dates are typed pure ``Date`` (WS-5 convention). ``estimated_due_date`` is
    the Naegele DPP (LMP + 280 days), stored so the episode keeps the value the
    caregiver saw; ``ultrasound_due_date`` is the optional correction by an
    early ultrasound, and *prevails* over the Naegele estimate when present
    (**OB-RSK-1**). Gestational age is always derived on demand for an explicit
    ``as_of`` date — see ``app.services.gestation``.
    """

    __tablename__ = "pregnancies"
    __table_args__ = (
        # A patient cannot have two episodes anchored on the exact same LMP.
        # NULL lmp_date stays allowed (unknown DUM) — Postgres treats NULLs as
        # distinct, so this only guards real duplicates.
        UniqueConstraint("patient_id", "lmp_date", name="uq_pregnancies_patient_lmp"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default=PregnancyStatus.active, nullable=False)
    # DUM — last menstrual period. Nullable: often unknown at first contact.
    lmp_date: Mapped[date | None] = mapped_column(Date)
    # DPP by Naegele (lmp_date + 280 days). Derived on create, stored.
    estimated_due_date: Mapped[date | None] = mapped_column(Date)
    # Early-ultrasound correction of the DPP (OB-RSK-1) — prevails when set.
    ultrasound_due_date: Mapped[date | None] = mapped_column(Date)
    ultrasound_date: Mapped[date | None] = mapped_column(Date)
    # When the episode ended (delivery/loss) — nullable while active.
    ended_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
