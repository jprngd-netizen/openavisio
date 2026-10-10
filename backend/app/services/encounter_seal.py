"""Seal/version helpers for a consultation note (WS-6).

The immutable seal of a clinical note must be reproducible and verifiable:
the same content must always hash to the same digest, and anyone holding the
stored snapshot must be able to recompute that digest. That requires a single,
stable canonicalisation of the JSON, which is what this module owns.

The functions here are deliberately dependency-free (stdlib only) so the ORM
model can import them to expose ``modified_since_signed`` without creating an
import cycle between models and services.
"""

import hashlib
import json

# The content fields of a consultation note that are sealed. Order is
# irrelevant for the hash (keys are sorted), but keeping a single list avoids
# the snapshot drifting from the DTO by accident.
SNAPSHOT_FIELDS = (
    "encounter_type",
    "encounter_date",
    "chief_complaint",
    "history",
    "physical_exam",
    "assessment",
    "plan",
    "notes",
)


def _iso(value) -> str | None:
    """Stable ISO-8601 form of a datetime (or None). Trimmed of microseconds?

    Microseconds are kept: they were written by the ORM and are part of the
    instant; the seal certifies the record as captured, not a rounded view.
    """
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def build_snapshot(*, diagnoses, **fields) -> dict:
    """Canonical content snapshot: the note's fields plus its diagnoses.

    ``diagnoses`` is an iterable of objects/mappings exposing ``cid10_code`` and
    ``cid10_display`` (the CID-10 snapshot as it read at that visit). They are
    sorted so two identical clinical records always seal to the same hash
    regardless of insertion order.
    """
    rows = []
    for d in diagnoses or []:
        if isinstance(d, dict):
            code, display = d.get("cid10_code"), d.get("cid10_display")
        else:
            code, display = d.cid10_code, d.cid10_display
        rows.append({"cid10_code": code, "cid10_display": display})
    rows.sort(key=lambda r: (r["cid10_code"] or "", r["cid10_display"] or ""))

    content = {k: fields.get(k) for k in SNAPSHOT_FIELDS}
    content["diagnoses"] = rows
    return content


def snapshot_from_encounter(encounter) -> dict:
    """Build the seal snapshot from an ``Encounter`` ORM instance.

    Reads the current content fields and its (non-deleted) diagnoses, so the
    same call both seals a fresh version and detects whether the note changed
    since its last seal.
    """
    return build_snapshot(
        diagnoses=encounter.diagnoses,
        encounter_type=encounter.encounter_type,
        encounter_date=_iso(encounter.encounter_date),
        chief_complaint=encounter.chief_complaint,
        history=encounter.history,
        physical_exam=encounter.physical_exam,
        assessment=encounter.assessment,
        plan=encounter.plan,
        notes=encounter.notes,
    )


def content_hash(content: dict) -> str:
    """SHA-256 hex digest of a snapshot.

    The JSON is canonicalised (keys sorted, compact separators, UTF-8,
    non-ASCII kept literal) so the digest is deterministic and independent of
    dict insertion order or incidental whitespace.
    """
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
