"""Allergy alert — substance matching between active allergies and a prescription (WS-1).

Pure domain logic: no SQL, no HTTP. The v1 matcher is deliberately simple
(there is no external drug database yet):

* normalize substrings by lower-casing, stripping accents (Unicode NFD) and
  removing every whitespace character;
* an allergy conflicts with a substance when the normalized names are equal, or
  when one contains the other and both are at least ``MIN_TOKEN_LEN`` chars —
  enough to catch e.g. ``Dipirona`` ↔ ``Dipirona sódica`` without matching
  trivial short tokens.

Only *active* allergies participate: an inactive/resolved record never raises a
prescription alert.
"""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from collections.abc import Iterable, Sequence

from app.models.allergy import Allergy, AllergyClinicalStatus

# Names shorter than this never match by containment (only by exact equality).
MIN_TOKEN_LEN = 4


def normalize_substance(value: str | None) -> str:
    """Lower-case, accent-fold and strip all whitespace from a substance name."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(without_accents.lower().split())


def substances_conflict(substance: str | None, other: str | None) -> bool:
    """Whether two substance names refer to the same substance (v1 heuristic)."""
    a, b = normalize_substance(substance), normalize_substance(other)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < MIN_TOKEN_LEN or len(b) < MIN_TOKEN_LEN:
        return False
    return a in b or b in a


@dataclass(frozen=True)
class AllergyConflict:
    """A prescription substance that collides with one active allergy."""

    allergy_id: uuid.UUID
    substance_display: str
    reaction: str | None
    severity: str | None
    criticality: str
    matched_substance: str


def active_allergies(allergies: Iterable[Allergy]) -> list[Allergy]:
    return [a for a in allergies if a.clinical_status == AllergyClinicalStatus.active]


def find_allergy_conflicts(
    allergies: Iterable[Allergy],
    substances: Sequence[str | None],
) -> list[AllergyConflict]:
    """Return one conflict per active allergy that matches any prescription item.

    ``allergies`` is the candidate list (only the active ones are considered);
    ``substances`` are the free-text medication names on the prescription.
    """
    cleaned = [s for s in substances if s and s.strip()]
    conflicts: list[AllergyConflict] = []
    for allergy in active_allergies(allergies):
        for substance in cleaned:
            if substances_conflict(allergy.substance_display, substance):
                conflicts.append(
                    AllergyConflict(
                        allergy_id=allergy.id,
                        substance_display=allergy.substance_display,
                        reaction=allergy.reaction,
                        severity=allergy.severity,
                        criticality=allergy.criticality,
                        matched_substance=substance,
                    )
                )
                break
    return conflicts
