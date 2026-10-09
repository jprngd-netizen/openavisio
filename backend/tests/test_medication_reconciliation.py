"""Unit tests for the active-medication reconciliation service (WS-2), no DB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.models.medication import MedicationStatement
from app.services.medication_reconciliation import (
    active_medications,
    duplicate_ids,
    find_duplicates,
    is_effective_at,
)

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)


def _med(
    display: str,
    *,
    status: str = "active",
    start: datetime | None = None,
    end: datetime | None = None,
    med_id: uuid.UUID | None = None,
) -> MedicationStatement:
    return MedicationStatement(
        id=med_id or uuid.uuid4(),
        patient_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        status=status,
        medication_display=display,
        effective_start=start,
        effective_end=end,
    )


def test_only_active_status_and_current_window_are_included() -> None:
    ongoing = _med("Valproat", start=NOW - timedelta(days=10))
    not_started = _med("Melatonin", start=NOW + timedelta(days=1))
    ended = _med("Ibuprofen", start=NOW - timedelta(days=30), end=NOW - timedelta(days=1))
    stopped = _med("Folsäure", status="stopped", start=NOW - timedelta(days=5))
    completed = _med("Amoxicilina", status="completed")
    on_hold = _med("Risperidon", status="on-hold")
    undated = _med("Vitamin D")  # no window at all

    active = active_medications(
        [ongoing, not_started, ended, stopped, completed, on_hold, undated], NOW
    )
    assert {m.medication_display for m in active} == {"Valproat", "Vitamin D"}


def test_window_boundaries_are_inclusive() -> None:
    assert is_effective_at(_med("A", start=NOW), NOW) is True
    assert is_effective_at(_med("A", end=NOW), NOW) is True
    assert is_effective_at(_med("A", start=NOW + timedelta(seconds=1)), NOW) is False
    assert is_effective_at(_med("A", end=NOW - timedelta(seconds=1)), NOW) is False


def test_naive_dates_are_read_as_sao_paulo() -> None:
    # legacy rows carried no tz; a naive start in the past must still count
    naive_past = _med("Valproat", start=datetime(2020, 1, 1, 0, 0))
    naive_future = _med("Melatonin", start=datetime(2030, 1, 1, 0, 0))
    active = active_medications([naive_past, naive_future], NOW)
    assert [m.medication_display for m in active] == ["Valproat"]


def test_find_duplicates_pairs_conflicting_substances_once() -> None:
    a = _med("Dipirona")
    b = _med("Dipirona sódica")
    c = _med("Paracetamol")
    pairs = find_duplicates([a, b, c])
    assert len(pairs) == 1
    first, second = pairs[0]
    assert {first.id, second.id} == {a.id, b.id}


def test_no_duplicates_for_distinct_or_short_substances() -> None:
    # "AAS" is too short to wildcard-match; only equality counts (allergy heuristic)
    assert find_duplicates([_med("AAS"), _med("AASNE")]) == []
    assert find_duplicates([_med("Dipirona"), _med("Paracetamol")]) == []
    assert find_duplicates([_med("Dipirona")]) == []


def test_equality_duplicate_accent_and_case_insensitive() -> None:
    a = _med("Dipirona")
    b = _med("dipirona")
    assert len(find_duplicates([a, b])) == 1


def test_duplicate_ids_maps_both_directions() -> None:
    a = _med("Amoxicilina")
    b = _med("Amoxicilina + Clavulanato")
    c = _med("Paracetamol")
    index = duplicate_ids([a, b, c])
    assert index[a.id] == [b.id]
    assert index[b.id] == [a.id]
    assert c.id not in index


def test_shared_base_matches_each_salt_but_salts_do_not_match_each_other() -> None:
    # the bare name contains both salts; the two salts don't contain each other
    a = _med("Dipirona")
    b = _med("Dipirona sódica")
    c = _med("Dipirona monoidratada")
    index = duplicate_ids([a, b, c])
    assert set(index[a.id]) == {b.id, c.id}
    assert index[b.id] == [a.id]
    assert index[c.id] == [a.id]
