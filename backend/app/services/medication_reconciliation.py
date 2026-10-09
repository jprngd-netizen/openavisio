"""Active-medication reconciliation (WS-2 — prontuário hardening).

Pure domain logic: no SQL, no HTTP. It answers two questions:

* **which medications are active *right now*** — only ``status == "active"``
  rows, and only while they are currently effective: an ``effective_start`` in
  the future is not active yet, an ``effective_end`` in the past is over. A
  window that is left open (``None``) is treated as unbounded on that side.

* **which of them are duplicates** — two active medications whose substance
  names refer to the same drug. The matcher is deliberately the *same* v1
  heuristic used for the allergy alert (WS-1): normalize by lower-casing,
  accent-folding (NFD) and stripping whitespace, then match by equality or by
  containment with a minimum-length guard. It is reused rather than
  re-implemented so allergies and medications agree on what "same substance"
  means.

Duplicate detection does **not** involve any external database, so it is safe
to run on every encounter open.

v1 scope — DEC-2
----------------
Drug–drug **interaction** checking is intentionally out of scope: a real
interaction database is an external dependency the plan defers (DEC-2). The
extension point is marked in :func:`find_duplicates`; wiring an interaction
source later must not change this module's public functions.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from app.core.datetimes import SAO_PAULO
from app.models.medication import MedicationStatement
from app.services.allergy_alert import substances_conflict

# The status that means "currently prescribed" — everything else (stopped,
# completed, on-hold) is excluded from the active list.
ACTIVE_STATUS = "active"


def _as_aware(dt: datetime) -> datetime:
    """Read a naive instant in America/Sao_Paulo (legacy rows had no tz)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=SAO_PAULO)


def is_effective_at(med: MedicationStatement, now: datetime) -> bool:
    """Whether the medication's validity window covers ``now``.

    An unbounded side (``None``) never disqualifies the row.
    """
    if med.effective_start is not None and _as_aware(med.effective_start) > now:
        return False
    if med.effective_end is not None and _as_aware(med.effective_end) < now:
        return False
    return True


def active_medications(
    meds: Iterable[MedicationStatement], now: datetime
) -> list[MedicationStatement]:
    """Medications that are both marked active and currently in force."""
    return [m for m in meds if m.status == ACTIVE_STATUS and is_effective_at(m, now)]


def find_duplicates(
    meds: Iterable[MedicationStatement],
) -> list[tuple[MedicationStatement, MedicationStatement]]:
    """Every unordered pair of medications that share a substance, once.

    ``meds`` is expected to be the *active* list; pass it through
    :func:`active_medications` first. Duplicate detection is symmetric, so each
    conflicting pair is reported a single time (a↔b, never also b↔a).

    Extension point (DEC-2): interaction checks — e.g. ``find_interactions``
    backed by an external drug database — would be a *separate* function here,
    leaving this one focused on duplicates only.
    """
    items = list(meds)
    duplicates: list[tuple[MedicationStatement, MedicationStatement]] = []
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            if substances_conflict(a.medication_display, b.medication_display):
                duplicates.append((a, b))
    return duplicates


def duplicate_ids(meds: Iterable[MedicationStatement]) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Map each duplicated medication id to the ids it conflicts with.

    Medications without a duplicate are absent from the mapping (the caller
    reads it with ``.get(id, [])``).
    """
    index: dict[uuid.UUID, list[uuid.UUID]] = {}
    for a, b in find_duplicates(meds):
        index.setdefault(a.id, []).append(b.id)
        index.setdefault(b.id, []).append(a.id)
    return index
