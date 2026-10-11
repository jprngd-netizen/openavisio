"""Unit tests for the gestational dating rules (OB-1 / OB-RSK-1).

Boundary cases for Naegele (LMP + 280 days) and for the gestational age derived
for an explicit ``as_of`` date. The ultrasound-corrected DPP must prevail.
"""

from __future__ import annotations

from datetime import date

from app.services.gestation import (
    effective_due_date,
    gestational_age,
    naegele_due_date,
)


def test_naegele_is_lmp_plus_280_days() -> None:
    assert naegele_due_date(date(2026, 1, 1)) == date(2026, 10, 8)
    # Across a year boundary.
    assert naegele_due_date(date(2025, 12, 31)) == date(2026, 10, 7)
    # Leap year: Feb 29 is a valid LMP.
    assert naegele_due_date(date(2024, 2, 29)) == date(2024, 12, 5)


def test_effective_due_date_prefers_ultrasound() -> None:
    assert effective_due_date(lmp_date=None, ultrasound_due_date=None) is None
    assert effective_due_date(lmp_date=date(2026, 1, 1)) == (date(2026, 10, 8), "lmp")
    # The corrected DPP wins even when an LMP exists.
    assert effective_due_date(
        lmp_date=date(2026, 1, 1), ultrasound_due_date=date(2026, 10, 20)
    ) == (date(2026, 10, 20), "ultrasound")
    # Ultrasound alone is a valid basis.
    assert effective_due_date(ultrasound_due_date=date(2026, 10, 20)) == (
        date(2026, 10, 20),
        "ultrasound",
    )


def test_gestational_age_at_edd_is_40_weeks() -> None:
    ga = gestational_age(date(2026, 10, 8), lmp_date=date(2026, 1, 1))
    assert ga is not None
    assert (ga.weeks, ga.days, ga.total_days, ga.basis) == (40, 0, 280, "lmp")


def test_gestational_age_at_lmp_is_zero() -> None:
    ga = gestational_age(date(2026, 1, 1), lmp_date=date(2026, 1, 1))
    assert ga is not None
    assert (ga.weeks, ga.days, ga.total_days) == (0, 0, 0)


def test_gestational_age_midpregnancy_weeks_and_days() -> None:
    # 2026-01-01 + 70 days -> 10w0d.
    ga = gestational_age(date(2026, 3, 12), lmp_date=date(2026, 1, 1))
    assert ga is not None
    assert (ga.weeks, ga.days, ga.total_days) == (10, 0, 70)
    # One day later -> 10w1d.
    ga = gestational_age(date(2026, 3, 13), lmp_date=date(2026, 1, 1))
    assert ga is not None
    assert (ga.weeks, ga.days) == (10, 1)


def test_gestational_age_uses_ultrasound_correction() -> None:
    ga = gestational_age(
        date(2026, 6, 1),
        lmp_date=date(2026, 1, 1),
        ultrasound_due_date=date(2026, 10, 20),
    )
    assert ga is not None
    assert (ga.weeks, ga.days, ga.total_days, ga.basis) == (19, 6, 139, "ultrasound")


def test_gestational_age_post_term_exceeds_40_weeks() -> None:
    # 7 days after the EDD -> 41w0d (not clamped).
    ga = gestational_age(date(2026, 10, 15), lmp_date=date(2026, 1, 1))
    assert ga is not None
    assert (ga.weeks, ga.days, ga.total_days) == (41, 0, 287)


def test_gestational_age_without_basis_is_none() -> None:
    assert gestational_age(date(2026, 6, 1)) is None
