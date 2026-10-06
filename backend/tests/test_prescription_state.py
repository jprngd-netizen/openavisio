"""Tests for the pure prescription state machine — transition matrix, invariants, version guard."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.prescriptions.state import (
    InvalidTransition,
    StalePrescription,
    can_edit_items,
    can_transition,
    check_version,
    set_memed_id,
    set_memed_uuid,
    transition,
)


def make_prescription(**overrides):
    """Create a minimal prescription-like object for pure state tests.

    SQLAlchemy default= applies at flush, not construction — so we set
    explicit defaults here for every field the state machine touches.
    """
    defaults = {
        "status": "draft",
        "version": 1,
        "memed_prescription_id": None,
        "memed_prescription_uuid": None,
        "issued_at": None,
        "document": None,
        "notes": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# Transition matrix — every legal pair allowed, every illegal pair raises
# ──────────────────────────────────────────────────────────────────────────────


class TestTransitionLegal:
    """Every legal transition in the matrix must succeed."""

    def test_draft_to_issued(self):
        p = make_prescription(memed_prescription_id="42", document=object())
        result = transition(p, "issued")
        assert result.status == "issued"
        assert result is p  # mutated in place

    def test_draft_to_failed(self):
        p = make_prescription()
        result = transition(p, "failed")
        assert result.status == "failed"

    def test_draft_to_deleted(self):
        p = make_prescription()
        result = transition(p, "deleted")
        assert result.status == "deleted"

    def test_failed_to_draft(self):
        p = make_prescription(status="failed")
        result = transition(p, "draft")
        assert result.status == "draft"

    def test_failed_to_deleted(self):
        p = make_prescription(status="failed")
        result = transition(p, "deleted")
        assert result.status == "deleted"

    def test_issued_to_deleted(self):
        p = make_prescription(status="issued", issued_at=datetime.now(timezone.utc))
        result = transition(p, "deleted")
        assert result.status == "deleted"


class TestTransitionIllegal:
    """Every illegal transition must raise InvalidTransition."""

    def test_draft_to_draft_raises(self):
        p = make_prescription()
        with pytest.raises(InvalidTransition):
            transition(p, "draft")

    def test_issued_to_draft_raises(self):
        p = make_prescription(status="issued")
        with pytest.raises(InvalidTransition):
            transition(p, "draft")

    def test_issued_to_failed_raises(self):
        p = make_prescription(status="issued")
        with pytest.raises(InvalidTransition):
            transition(p, "failed")

    def test_issued_to_issued_raises(self):
        p = make_prescription(status="issued")
        with pytest.raises(InvalidTransition):
            transition(p, "issued")

    def test_failed_to_issued_succeeds(self):
        """failed → issued is legal for re-archive after a signed-but-unarchived failure."""
        p = make_prescription(
            status="failed",
            memed_prescription_id="42",
            document=object(),
        )
        result = transition(p, "issued")
        assert result.status == "issued"

    def test_failed_to_failed_raises(self):
        p = make_prescription(status="failed")
        with pytest.raises(InvalidTransition):
            transition(p, "failed")

    def test_deleted_to_draft_raises(self):
        p = make_prescription(status="deleted")
        with pytest.raises(InvalidTransition):
            transition(p, "draft")

    def test_deleted_to_issued_raises(self):
        p = make_prescription(status="deleted")
        with pytest.raises(InvalidTransition):
            transition(p, "issued")

    def test_deleted_to_failed_raises(self):
        p = make_prescription(status="deleted")
        with pytest.raises(InvalidTransition):
            transition(p, "failed")

    def test_deleted_to_deleted_raises(self):
        p = make_prescription(status="deleted")
        with pytest.raises(InvalidTransition):
            transition(p, "deleted")


class TestCanTransitionHelper:
    """can_transition() returns bool without raising."""

    def test_legal_pairs(self):
        assert can_transition("draft", "issued") is True
        assert can_transition("draft", "failed") is True
        assert can_transition("draft", "deleted") is True
        assert can_transition("failed", "draft") is True
        assert can_transition("failed", "issued") is True
        assert can_transition("failed", "deleted") is True
        assert can_transition("issued", "deleted") is True

    def test_illegal_pairs(self):
        assert can_transition("draft", "draft") is False
        assert can_transition("issued", "draft") is False
        assert can_transition("issued", "failed") is False
        assert can_transition("issued", "issued") is False
        assert can_transition("failed", "failed") is False
        assert can_transition("deleted", "draft") is False
        assert can_transition("deleted", "issued") is False
        assert can_transition("deleted", "failed") is False
        assert can_transition("deleted", "deleted") is False

    def test_unknown_status(self):
        assert can_transition("nonexistent", "draft") is False


# ──────────────────────────────────────────────────────────────────────────────
# Invariants
# ──────────────────────────────────────────────────────────────────────────────


class TestInvariantIssuedRequiresMemedId:
    """issued requires memed_prescription_id."""

    def test_missing_memed_id_raises(self):
        p = make_prescription(document=object())  # no memed_prescription_id
        with pytest.raises(ValueError, match="memed_prescription_id"):
            transition(p, "issued")


class TestInvariantIssuedRequiresDocument:
    """issued requires a PrescriptionDocument."""

    def test_missing_document_raises(self):
        p = make_prescription(memed_prescription_id="42")  # no document
        with pytest.raises(ValueError, match="PrescriptionDocument"):
            transition(p, "issued")


class TestInvariantIssuedAt:
    """issued_at is set on transition to issued and is write-once."""

    def test_issued_sets_issued_at(self):
        p = make_prescription(memed_prescription_id="42", document=object())
        assert p.issued_at is None
        transition(p, "issued")
        assert p.issued_at is not None
        assert p.issued_at.tzinfo is not None  # timezone-aware

    def test_issued_at_write_once(self):
        """Re-issuing (failed→draft→issued) must not overwrite issued_at."""
        fixed = datetime(2026, 10, 5, tzinfo=timezone.utc)
        p = make_prescription(
            status="failed",
            memed_prescription_id="42",
            document=object(),
            issued_at=fixed,
        )
        transition(p, "draft")
        transition(p, "issued")
        assert p.issued_at == fixed


class TestInvariantCanEditItems:
    """Items are editable only when status == 'draft'."""

    def test_draft_allows_edit(self):
        assert can_edit_items(make_prescription()) is True

    def test_issued_blocks_edit(self):
        assert can_edit_items(make_prescription(status="issued")) is False

    def test_failed_blocks_edit(self):
        assert can_edit_items(make_prescription(status="failed")) is False

    def test_deleted_blocks_edit(self):
        assert can_edit_items(make_prescription(status="deleted")) is False


class TestInvariantMemedIdsWriteOnce:
    """Memed prescription IDs are write-once."""

    def test_set_memed_id_first_time(self):
        p = make_prescription()
        set_memed_id(p, "42")
        assert p.memed_prescription_id == "42"

    def test_set_memed_id_second_time_raises(self):
        p = make_prescription()
        set_memed_id(p, "42")
        with pytest.raises(ValueError, match="write-once"):
            set_memed_id(p, "99")

    def test_set_memed_uuid_first_time(self):
        p = make_prescription()
        set_memed_uuid(p, "abc-123")
        assert p.memed_prescription_uuid == "abc-123"

    def test_set_memed_uuid_second_time_raises(self):
        p = make_prescription()
        set_memed_uuid(p, "abc-123")
        with pytest.raises(ValueError, match="write-once"):
            set_memed_uuid(p, "def-456")


# ──────────────────────────────────────────────────────────────────────────────
# Optimistic concurrency guard
# ──────────────────────────────────────────────────────────────────────────────


class TestCheckVersion:
    """check_version guards against stale writes."""

    def test_matching_version_passes(self):
        p = make_prescription(version=3)
        check_version(p, 3)  # must not raise

    def test_mismatch_raises_stale(self):
        p = make_prescription(version=3)
        with pytest.raises(StalePrescription) as exc:
            check_version(p, 1)
        assert exc.value.current_version == 3
        assert exc.value.expected_version == 1

    def test_stale_message_contains_versions(self):
        p = make_prescription(version=5)
        try:
            check_version(p, 2)
        except StalePrescription as e:
            msg = str(e)
            assert "5" in msg
            assert "2" in msg

    def test_default_version_is_one(self):
        p = make_prescription()
        check_version(p, 1)  # must not raise