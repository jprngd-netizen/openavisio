import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
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


class FetalPresentation(StrEnum):
    """Presenting part at the prenatal visit (nullable = not assessed yet)."""

    cephalic = "cephalic"
    breech = "breech"
    transverse = "transverse"
    oblique = "oblique"
    variable = "variable"
    not_assessed = "not_assessed"


class EdemaSeverity(StrEnum):
    """Lower-limb edema grade (a pre-eclampsia screening signal)."""

    none = "none"
    mild = "mild"
    moderate = "moderate"
    severe = "severe"


class Proteinuria(StrEnum):
    """Dipstick proteinuria (a pre-eclampsia screening signal)."""

    negative = "negative"
    trace = "trace"
    plus1 = "plus1"
    plus2 = "plus2"
    plus3 = "plus3"
    plus4 = "plus4"


class PregnancyVisit(OwnedResource):
    """A prenatal consultation recorded against a ``Pregnancy`` episode (OB-2).

    A *visit* is not an ``Encounter``: it is a dated obstetric record whose
    obstetric measurements only make sense next to the episode they belong to
    (**OB-DEC-2**). Following the plan's "the record is a snapshot of its date"
    principle, ``visit_date`` is the date the measurements were taken and the
    one date the record is anchored to; the gestational age shown for a visit
    is derived *for that date* (``as_of=visit_date``), never for "today" — see
    ``app.services.gestation``. ``visit_date`` is unique per episode (a
    same-day duplicate visit is a data-entry error).

    PA/weight are deliberately **not** duplicated here: they are vitals (WS-4 /
    OB-4) and already have a single source of truth (``observations``). This
    resource keeps only the obstetric fields that have no home elsewhere.
    """

    __tablename__ = "pregnancy_visits"
    __table_args__ = (
        UniqueConstraint("pregnancy_id", "visit_date", name="uq_pregnancy_visits_pregnancy_date"),
    )

    pregnancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pregnancies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Day of the consultation — the anchor the record's GA is computed for.
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fundal_height_cm: Mapped[float | None] = mapped_column(Numeric(5, 1))
    fetal_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    presentation: Mapped[str | None] = mapped_column(String(30))
    edema: Mapped[str | None] = mapped_column(String(20))
    proteinuria: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
