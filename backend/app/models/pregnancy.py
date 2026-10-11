import uuid
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, OwnedResource

if TYPE_CHECKING:
    from app.models.condition import Condition


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


class PregnancyOutcomeType(StrEnum):
    """Complete outcome taxonomy for an obstetric episode (**OB-DEC-3**).

    Covers the full approved vocabulary — a term/cesarean for a live birth, and
    every loss (miscarriage, induced abortion, ectopic, fetal death/``natimorto``).
    The delivery route (vaginal vs cesarean) is encoded in the type itself so
    there is a single source of truth for the mode; the episode status never
    needs a lossy ``completed/miscarriage`` collapse.
    """

    vaginal_delivery = "vaginal_delivery"
    cesarean_delivery = "cesarean_delivery"
    miscarriage = "miscarriage"
    induced_abortion = "induced_abortion"
    ectopic = "ectopic"
    fetal_death = "fetal_death"


class NewbornSex(StrEnum):
    """Sex recorded for a live newborn (nullable — often not charted at once)."""

    female = "female"
    male = "male"
    unknown = "unknown"


# Outcomes that deliver a live newborn and therefore carry the RN fields.
LIVE_BIRTH_OUTCOMES = frozenset(
    {PregnancyOutcomeType.vaginal_delivery, PregnancyOutcomeType.cesarean_delivery}
)

# Registering an outcome *closes* the episode (OB-3): the terminal status is the
# adequate one for the loss/term — never a blanket ``completed``.
OUTCOME_STATUS: dict[str, PregnancyStatus] = {
    PregnancyOutcomeType.vaginal_delivery: PregnancyStatus.completed,
    PregnancyOutcomeType.cesarean_delivery: PregnancyStatus.completed,
    PregnancyOutcomeType.miscarriage: PregnancyStatus.miscarriage,
    PregnancyOutcomeType.induced_abortion: PregnancyStatus.terminated,
    PregnancyOutcomeType.ectopic: PregnancyStatus.ectopic,
    PregnancyOutcomeType.fetal_death: PregnancyStatus.fetal_death,
}


class PregnancyOutcome(OwnedResource):
    """The dated, frozen outcome that closes a ``Pregnancy`` episode (OB-3).

    A **separate 1:1 table** rather than columns embedded in ``Pregnancy``: the
    outcome is a record of its own with a date it is anchored to, and it either
    exists (the episode is closed) or it does not (the episode is open) — the
    unique constraint on ``pregnancy_id`` makes "at most one outcome per
    gestation" a database invariant, so a second registration can never happen
    even under a race. Following the "the record is a snapshot of its date"
    principle, the gestational age *at the outcome* is derived for
    ``as_of=outcome_date`` (see ``app.services.gestation``), never stored and
    never computed for "today".

    The newborn fields (``newborn_weight_g`` / ``apgar_*`` / ``newborn_sex``)
    are only meaningful for a live birth; for a loss they are NULL (enforced by
    the create schema).
    """

    __tablename__ = "pregnancy_outcomes"
    __table_args__ = (
        # 1:1 with the episode; also the idempotency guard for "one outcome only".
        UniqueConstraint("pregnancy_id", name="uq_pregnancy_outcomes_pregnancy"),
    )

    pregnancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pregnancies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome_type: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Newborn data — live birth only (NULL for losses).
    newborn_weight_g: Mapped[int | None] = mapped_column(Integer)
    apgar_1: Mapped[int | None] = mapped_column(Integer)
    apgar_5: Mapped[int | None] = mapped_column(Integer)
    newborn_sex: Mapped[str | None] = mapped_column(String(20))
    # Intercorrências / free-text notes about the outcome.
    notes: Mapped[str | None] = mapped_column(Text)


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


class PregnancyCondition(BaseModel):
    """An intercorrência (gestational diagnosis) linked to a ``Pregnancy`` (OB-4).

    Mirrors ``EncounterCondition`` (WS-3): the episode cites the patient's
    canonical problem-list ``Condition`` — find-or-created by
    ``(patient_id, code)`` through ``app.services.encounter_diagnoses`` (reused,
    not reimplemented) — so DMG, pre-eclampsia, etc. show up in the problem list
    with the gestation as their origin. The CID-10 snapshot
    (``cid10_code``/``cid10_display``) is kept as it read when linked, so renaming
    the Condition later does not rewrite history. The Condition is **never
    deleted**; removing an intercorrência soft-deletes only this link.
    """

    __tablename__ = "pregnancy_conditions"
    __table_args__ = (UniqueConstraint("pregnancy_id", "condition_id"),)

    pregnancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pregnancies.id"), nullable=False, index=True
    )
    condition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conditions.id"), nullable=False, index=True
    )
    cid10_code: Mapped[str | None] = mapped_column(String(20))
    cid10_display: Mapped[str | None] = mapped_column(String(256))

    condition: Mapped["Condition"] = relationship("Condition", viewonly=True)  # noqa: F821
    pregnancy: Mapped["Pregnancy"] = relationship("Pregnancy", viewonly=True)
