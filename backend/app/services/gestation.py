"""Gestational-age and due-date calculations (OB-1 / OB-RSK-1).

Design principle (plan addendum): **the record is a snapshot of its date**. A
gestational age is only meaningful relative to *a* date, so every function here
takes an explicit ``as_of`` — nothing defaults to "today". A live panel may pass
today; a sealed/ended episode passes its own date. Never hide a ``date.today()``
in here.

Rules adopted:

* **Naegele**: ``estimated_due_date = lmp_date + 280 days`` (OB-RSK-1).
* **Ultrasound correction prevails**: when an early-ultrasound corrected DPP is
  present (``ultrasound_due_date``) it overrides the Naegele estimate for both
  the due date and the gestational age, because dating by early USG is more
  accurate than the reported LMP.
* **Gestational age** in weeks+days: ``total_days = 280 - (due_date - as_of).days``
  where ``due_date`` is the corrected DPP when present, else the Naegele DPP.
  ``total_days`` is returned alongside so callers never re-derive it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

NAEGELE_DAYS = 280  # 40 weeks


@dataclass(frozen=True)
class GestationalAge:
    """A gestational age as weeks + days, computed for a specific ``as_of`` date."""

    weeks: int
    days: int
    total_days: int
    as_of: date
    basis: str  # "lmp" (Naegele) or "ultrasound" (early-USG corrected)


def naegele_due_date(lmp_date: date) -> date:
    """Estimate the due date from the last menstrual period (DUM + 280 days)."""
    return lmp_date + timedelta(days=NAEGELE_DAYS)


def effective_due_date(
    *,
    lmp_date: date | None = None,
    ultrasound_due_date: date | None = None,
) -> tuple[date, str] | None:
    """Return ``(due_date, basis)`` preferring the ultrasound correction.

    ``basis`` is ``"ultrasound"`` when the corrected DPP prevails, else
    ``"lmp"``. ``None`` when neither the DUM nor a corrected DPP is known.
    """
    if ultrasound_due_date is not None:
        return ultrasound_due_date, "ultrasound"
    if lmp_date is not None:
        return naegele_due_date(lmp_date), "lmp"
    return None


def gestational_age(
    as_of: date,
    *,
    lmp_date: date | None = None,
    ultrasound_due_date: date | None = None,
) -> GestationalAge | None:
    """Gestational age on ``as_of``, preferring the ultrasound-corrected DPP.

    Returns ``None`` when there is no dating basis (no DUM and no corrected DPP).
    The value is pure arithmetic and is *not* clamped: an ``as_of`` after the due
    date yields > 280 days (post-term), and one before the LMP yields a negative
    ``total_days`` — callers that only expect plausible values validate the input.
    """
    effective = effective_due_date(lmp_date=lmp_date, ultrasound_due_date=ultrasound_due_date)
    if effective is None:
        return None
    due_date, basis = effective
    total_days = NAEGELE_DAYS - (due_date - as_of).days
    weeks, days = divmod(total_days, 7)
    return GestationalAge(weeks=weeks, days=days, total_days=total_days, as_of=as_of, basis=basis)


def display_gestational_age(
    pregnancy,
    *,
    as_of: date | None = None,
) -> GestationalAge | None:
    """Gestational age to *show* for an episode.

    The episode is a record: when it has ended, its age is frozen at ``ended_at``
    and ``as_of`` is ignored. While active, the caller decides the live date
    (``as_of``); we never fall back to today here.
    """
    anchor = pregnancy.ended_at or as_of
    if anchor is None:
        return None
    return gestational_age(
        anchor,
        lmp_date=pregnancy.lmp_date,
        ultrasound_due_date=pregnancy.ultrasound_due_date,
    )
