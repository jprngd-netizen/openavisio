"""Tests for the defensive Memed event adapter.

The ``prescricaoImpressa`` and ``prescricaoExcluida`` event payloads are
unverified at runtime — the adapter must try multiple candidate keys for
the prescription id and fail with a typed, recoverable error that lists
only key names (never values).
"""
from __future__ import annotations

import pytest

from app.services.prescriptions.events import (
    CaptureMetadata,
    UnparsableMemedEvent,
    parse_prescricao_excluida,
    parse_prescricao_impressa,
)


# ---------------------------------------------------------------------------
# CaptureMetadata dataclass
# ---------------------------------------------------------------------------


class TestCaptureMetadata:
    """CaptureMetadata must carry the expected fields."""

    def test_fields(self):
        meta = CaptureMetadata(
            memed_prescription_id="42",
            signed=True,
            file_name="receita.pdf",
            file_hash="abc123",
        )
        assert meta.memed_prescription_id == "42"
        assert meta.signed is True
        assert meta.file_name == "receita.pdf"
        assert meta.file_hash == "abc123"

    def test_optional_fields_default_to_none(self):
        meta = CaptureMetadata(memed_prescription_id="42", signed=False)
        assert meta.file_name is None
        assert meta.file_hash is None


# ---------------------------------------------------------------------------
# parse_prescricao_impressa — candidate keys for the prescription id
# ---------------------------------------------------------------------------
# Candidate keys (in priority order):
#   prescription_id, prescriptionId, prescription_uuid,
#   data.prescription_id, id (when type is a prescription)


class TestParsePrescricaoImpressaHappy:
    """Payloads with each candidate key must parse correctly."""

    def test_prescription_id_key(self):
        """candidate: prescription_id (int)"""
        payload = {"prescription_id": 42, "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "42"
        assert meta.signed is True

    def test_prescription_id_key_str(self):
        """candidate: prescription_id (str)"""
        payload = {"prescription_id": "42", "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "42"

    def test_prescription_id_key(self):
        """candidate: prescriptionId"""
        payload = {"prescriptionId": "presc_99", "signed": False}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "presc_99"
        assert meta.signed is False

    def test_prescription_uuid_key(self):
        """candidate: prescription_uuid"""
        payload = {"prescription_uuid": "uuid-abc-123", "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "uuid-abc-123"

    def test_data_dot_prescription_id_key(self):
        """candidate: data.prescription_id (nested)"""
        payload = {"data": {"prescription_id": "nested_42"}, "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "nested_42"

    def test_id_key_with_type_prescription(self):
        """candidate: id when type indicates a prescription"""
        payload = {"id": "presc_77", "type": "prescription", "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "presc_77"

    def test_id_key_without_type_does_not_match(self):
        """id without a type field should NOT be treated as a prescription id."""
        payload = {"id": "some_uuid", "signed": True}
        with pytest.raises(UnparsableMemedEvent):
            parse_prescricao_impressa(payload)

    def test_id_key_with_non_prescription_type_does_not_match(self):
        """id with type != 'prescription' should NOT match."""
        payload = {"id": "some_uuid", "type": "patient", "signed": True}
        with pytest.raises(UnparsableMemedEvent):
            parse_prescricao_impressa(payload)


class TestParsePrescricaoImpressaMetadata:
    """signed, file_name, file_hash candidate keys."""

    def test_signed_field(self):
        payload = {"prescription_id": "42", "signed": True}
        meta = parse_prescricao_impressa(payload)
        assert meta.signed is True

    def test_signed_defaults_false(self):
        payload = {"prescription_id": "42"}
        meta = parse_prescricao_impressa(payload)
        assert meta.signed is False

    def test_file_name_key(self):
        """candidate: file_name"""
        payload = {"prescription_id": "42", "file_name": "receita.pdf"}
        meta = parse_prescricao_impressa(payload)
        assert meta.file_name == "receita.pdf"

    def test_file_name_camelcase_key(self):
        """candidate: fileName"""
        payload = {"prescription_id": "42", "fileName": "receita.pdf"}
        meta = parse_prescricao_impressa(payload)
        assert meta.file_name == "receita.pdf"

    def test_file_hash_key(self):
        """candidate: file_hash"""
        payload = {"prescription_id": "42", "file_hash": "sha256abc"}
        meta = parse_prescricao_impressa(payload)
        assert meta.file_hash == "sha256abc"

    def test_file_hash_camelcase_key(self):
        """candidate: fileHash"""
        payload = {"prescription_id": "42", "fileHash": "sha256xyz"}
        meta = parse_prescricao_impressa(payload)
        assert meta.file_hash == "sha256xyz"

    def test_all_metadata_fields(self):
        """All metadata fields populated."""
        payload = {
            "prescription_id": "42",
            "signed": True,
            "file_name": "receita.pdf",
            "file_hash": "abc123def456",
        }
        meta = parse_prescricao_impressa(payload)
        assert meta.memed_prescription_id == "42"
        assert meta.signed is True
        assert meta.file_name == "receita.pdf"
        assert meta.file_hash == "abc123def456"


# ---------------------------------------------------------------------------
# parse_prescricao_excluida — returns the prescription id as a string
# ---------------------------------------------------------------------------


class TestParsePrescricaoExcluidaHappy:
    """Payloads with each candidate key must return the id."""

    def test_prescription_id_key(self):
        payload = {"prescription_id": 42}
        result = parse_prescricao_excluida(payload)
        assert result == "42"

    def test_prescriptionId_key(self):
        payload = {"prescriptionId": "presc_99"}
        result = parse_prescricao_excluida(payload)
        assert result == "presc_99"

    def test_prescription_uuid_key(self):
        payload = {"prescription_uuid": "uuid-abc"}
        result = parse_prescricao_excluida(payload)
        assert result == "uuid-abc"

    def test_data_dot_prescription_id_key(self):
        payload = {"data": {"prescription_id": "nested_42"}}
        result = parse_prescricao_excluida(payload)
        assert result == "nested_42"

    def test_id_key_with_type_prescription(self):
        payload = {"id": "presc_77", "type": "prescription"}
        result = parse_prescricao_excluida(payload)
        assert result == "presc_77"


# ---------------------------------------------------------------------------
# UnparsableMemedEvent — error behaviour
# ---------------------------------------------------------------------------


class TestUnparsableMemedEvent:
    """A payload without a prescription id must raise a typed, recoverable error."""

    def test_raises_on_empty_payload(self):
        with pytest.raises(UnparsableMemedEvent) as exc:
            parse_prescricao_impressa({})
        assert exc.type is UnparsableMemedEvent

    def test_error_contains_keys_not_values(self):
        """The str() must contain key names but NEVER the values."""
        payload = {"foo": "secret-value-42", "bar": "another-secret"}
        with pytest.raises(UnparsableMemedEvent) as exc:
            parse_prescricao_impressa(payload)
        msg = str(exc.value)
        # Must contain key names
        assert "foo" in msg
        assert "bar" in msg
        # Must NOT contain values
        assert "secret-value-42" not in msg
        assert "another-secret" not in msg

    def test_error_has_sorted_keys(self):
        payload = {"z": 1, "a": 2, "m": 3}
        with pytest.raises(UnparsableMemedEvent) as exc:
            parse_prescricao_impressa(payload)
        assert exc.value.keys == ["a", "m", "z"]

    def test_parse_prescricao_excluida_also_raises(self):
        with pytest.raises(UnparsableMemedEvent) as exc:
            parse_prescricao_excluida({"irrelevant": "data"})
        assert "irrelevant" in str(exc.value)
        assert "data" not in str(exc.value)

    def test_error_is_recoverable(self):
        """UnparsableMemedEvent is a standard Exception — catchable."""
        try:
            parse_prescricao_impressa({"unknown": "x"})
        except UnparsableMemedEvent:
            pass  # recoverable
        else:
            pytest.fail("Expected UnparsableMemedEvent")