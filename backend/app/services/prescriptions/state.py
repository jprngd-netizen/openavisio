"""Pure prescription state machine — no SQL, no HTTP, no DB imports.

Provides the transition table, invariant enforcement, and optimistic-concurrency
guard for the Prescription status machine.

Status machine::

    draft  → issued | failed | deleted
    failed → draft  | deleted
    issued → deleted
    deleted → (terminal)

Invariants enforced:
    - Items are editable only when ``status == "draft"``.
    - ``issued_at`` is write-once (set on transition to ``issued``, never
      overwritten).
    - ``issued`` requires ``memed_prescription_id`` **and** a
      ``PrescriptionDocument``.
    - Memed prescription IDs (``memed_prescription_id``,
      ``memed_prescription_uuid``) are write-once.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class InvalidTransition(ValueError):
    """Raised when a status transition is not in the allowed table."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from '{current}' to '{target}'")


class StalePrescription(ValueError):
    """Raised when an optimistic-concurrency check fails.

    The prescription was modified by another request between read and write.
    """

    def __init__(self, current_version: int, expected_version: int) -> None:
        self.current_version = current_version
        self.expected_version = expected_version
        super().__init__(
            f"Prescription version {current_version} does not match "
            f"expected {expected_version}"
        )


# Transition table: {current_status: {allowed_target_statuses}}
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"issued", "failed", "deleted"},
    "failed": {"draft", "issued", "deleted"},
    "issued": {"deleted"},
    "deleted": set(),  # terminal — no outgoing transitions
}


def can_transition(current: str, target: str) -> bool:
    """Check whether a transition is allowed, without raising."""
    allowed = _TRANSITIONS.get(current, set())
    return target in allowed


def transition(prescription: Any, target: str) -> Any:
    """Transition *prescription* to *target* status.

    Mutates the prescription in place and returns it.

    Raises:
        InvalidTransition: if the transition is not in the allowed table.
        ValueError: if an invariant is violated (missing
            ``memed_prescription_id`` or ``document`` when issuing).
    """
    current = prescription.status

    if not can_transition(current, target):
        raise InvalidTransition(current, target)

    # --- Invariant enforcement ---
    if target == "issued":
        _enforce_issue_invariants(prescription)

    # --- Mutation ---
    if target == "issued" and prescription.issued_at is None:
        prescription.issued_at = datetime.now(timezone.utc)

    prescription.status = target
    return prescription


def _enforce_issue_invariants(prescription: Any) -> None:
    """Check invariants required before transitioning to ``issued``."""
    if not prescription.memed_prescription_id:
        raise ValueError(
            "Cannot issue a prescription without memed_prescription_id"
        )
    if not prescription.document:
        raise ValueError(
            "Cannot issue a prescription without a PrescriptionDocument"
        )


def check_version(prescription: Any, expected: int) -> None:
    """Check that *prescription.version* matches *expected*.

    This is the read-side guard for optimistic concurrency.  The write-side
    compare-and-swap (``UPDATE … WHERE id=:id AND version=:expected`` with
    rowcount check) belongs in the router/service layer, not here.

    Raises:
        StalePrescription: if the version does not match.
    """
    if prescription.version != expected:
        raise StalePrescription(prescription.version, expected)


def can_edit_items(prescription: Any) -> bool:
    """Return True if items can be edited on this prescription.

    Items are only editable while the prescription is in ``draft`` status.
    """
    return prescription.status == "draft"


def set_memed_id(prescription: Any, value: str) -> None:
    """Set ``memed_prescription_id``, enforcing write-once semantics.

    If already set to the **same** value, this is a no-op (idempotent).
    A different value still raises ``ValueError``.
    """
    if prescription.memed_prescription_id is not None:
        if prescription.memed_prescription_id == value:
            return  # Idempotent — already set to the same value
        raise ValueError("memed_prescription_id is write-once")
    prescription.memed_prescription_id = value


def set_memed_uuid(prescription: Any, value: str) -> None:
    """Set ``memed_prescription_uuid``, enforcing write-once semantics."""
    if prescription.memed_prescription_uuid is not None:
        raise ValueError("memed_prescription_uuid is write-once")
    prescription.memed_prescription_uuid = value