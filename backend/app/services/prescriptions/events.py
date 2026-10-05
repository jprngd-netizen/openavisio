"""Defensive adapter for unverified Memed event payloads.

The ``prescricaoImpressa`` and ``prescricaoExcluida`` events arrive via
``postMessage`` from the Memed Sinapse Prescrição module. Their payload
structure is documented but **unverified at runtime** — the Memed module
may change key names, casing, or nesting between releases.

This module tries **multiple candidate keys** for the prescription id and
metadata fields, and raises a typed, recoverable error when the id cannot
be found. The error message contains **only key names** — never values —
to avoid leaking patient or prescription data into logs.

Candidate keys for the prescription id (tried in order):
    ``prescription_id`` — snake_case, most common in documented payloads
    ``prescriptionId``  — camelCase variant
    ``prescription_uuid`` — UUID-style identifier
    ``data.prescription_id`` — nested under a ``data`` envelope
    ``id`` — generic id, only accepted when ``type == "prescription"``

Candidate keys for metadata:
    ``signed`` — boolean, from the event payload
    ``file_name`` / ``fileName`` — the filename of the signed PDF
    ``file_hash`` / ``fileHash`` — hash from the event (algorithm unknown)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# CaptureMetadata — structured result of parsing prescricaoImpressa
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CaptureMetadata:
    """Metadata extracted from a ``prescricaoImpressa`` event payload.

    Fields:
        memed_prescription_id: The prescription identifier from the event.
        signed: Whether the Memed module reported the prescription as signed.
        file_name: The filename of the signed PDF (if provided).
        file_hash: A hash from the event payload (algorithm unknown — the
            archive service compares it only when it looks like SHA-256).
    """

    memed_prescription_id: str
    signed: bool = False
    file_name: str | None = field(default=None)
    file_hash: str | None = field(default=None)


# ---------------------------------------------------------------------------
# UnparsableMemedEvent — typed, recoverable error
# ---------------------------------------------------------------------------


class UnparsableMemedEvent(Exception):
    """Raised when a Memed event payload cannot be parsed.

    The ``keys`` attribute carries the **sorted** payload key names so that
    callers can log or inspect which keys were present. The ``__str__``
    representation contains **only key names** — never values — to prevent
    leaking patient or prescription data into logs or error responses.

    This is a **recoverable** error: callers should catch it and respond
    with a 4xx status, not crash the request.
    """

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        super().__init__(f"UnparsableMemedEvent: keys={keys}")

    def __str__(self) -> str:
        # Only key names — no values — to prevent data leakage.
        return f"UnparsableMemedEvent: keys={self.keys}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_extract_id(payload: dict[str, Any]) -> str | None:
    """Try candidate keys for the prescription id, returning the first match.

    Returns the id as a string, or ``None`` if no candidate key is found.
    """
    # 1. prescription_id (snake_case, most common)
    raw = payload.get("prescription_id")
    if raw is not None:
        return str(raw)

    # 2. prescriptionId (camelCase variant)
    raw = payload.get("prescriptionId")
    if raw is not None:
        return str(raw)

    # 3. prescription_uuid (UUID-style identifier)
    raw = payload.get("prescription_uuid")
    if raw is not None:
        return str(raw)

    # 4. data.prescription_id (nested under a data envelope)
    data = payload.get("data")
    if isinstance(data, dict):
        raw = data.get("prescription_id")
        if raw is not None:
            return str(raw)

    # 5. id — only when type == "prescription"
    if payload.get("type") == "prescription":
        raw = payload.get("id")
        if raw is not None:
            return str(raw)

    return None


def _try_extract_bool(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    """Extract a boolean value from *payload* by *key*, returning *default* if absent."""
    raw = payload.get(key)
    if isinstance(raw, bool):
        return raw
    return default


def _try_extract_str(
    payload: dict[str, Any], *candidates: str
) -> str | None:
    """Extract a string value from *payload* by trying *candidates* in order."""
    for key in candidates:
        raw = payload.get(key)
        if raw is not None:
            return str(raw)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_prescricao_impressa(payload: dict[str, Any]) -> CaptureMetadata:
    """Parse a ``prescricaoImpressa`` event payload into ``CaptureMetadata``.

    The payload is **unverified** — this function tries multiple candidate
    keys for the prescription id and metadata fields.

    Raises:
        UnparsableMemedEvent: if the prescription id cannot be found in the
            payload. The error message contains only key names, never values.
    """
    memed_prescription_id = _try_extract_id(payload)
    if memed_prescription_id is None:
        raise UnparsableMemedEvent(keys=sorted(payload.keys()))

    signed = _try_extract_bool(payload, "signed")
    file_name = _try_extract_str(payload, "file_name", "fileName")
    file_hash = _try_extract_str(payload, "file_hash", "fileHash")

    return CaptureMetadata(
        memed_prescription_id=memed_prescription_id,
        signed=signed,
        file_name=file_name,
        file_hash=file_hash,
    )


def parse_prescricao_excluida(payload: dict[str, Any]) -> str:
    """Parse a ``prescricaoExcluida`` event payload, returning the prescription id.

    The payload is **unverified** — this function tries multiple candidate
    keys for the prescription id.

    Returns:
        The prescription id as a string.

    Raises:
        UnparsableMemedEvent: if the prescription id cannot be found in the
            payload. The error message contains only key names, never values.
    """
    memed_prescription_id = _try_extract_id(payload)
    if memed_prescription_id is None:
        raise UnparsableMemedEvent(keys=sorted(payload.keys()))

    return memed_prescription_id