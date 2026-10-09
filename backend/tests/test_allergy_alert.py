"""Unit tests for the allergy-substance matcher (WS-1), no DB required."""

from __future__ import annotations

import uuid

from app.models.allergy import Allergy
from app.services.allergy_alert import (
    find_allergy_conflicts,
    normalize_substance,
    substances_conflict,
)


def _allergy(display: str, status: str = "active", **kw) -> Allergy:
    return Allergy(
        id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        substance_display=display,
        clinical_status=status,
        criticality=kw.get("criticality", "high"),
        reaction=kw.get("reaction"),
        severity=kw.get("severity"),
    )


def test_normalize_substance_folds_case_accents_and_spaces() -> None:
    assert normalize_substance(" Dipirona  Sódica ") == "dipironasodica"
    assert normalize_substance("Ácido Acetilsalicílico") == "acidoacetilsalicilico"
    assert normalize_substance(None) == ""
    assert normalize_substance("") == ""


def test_exact_normalized_match() -> None:
    assert substances_conflict("Dipirona", "dipirona")
    assert substances_conflict("Dipirona Sódica", "dipirona sodica")


def test_containment_match() -> None:
    # prescription carries the salt, allergy the base — same substance
    assert substances_conflict("Dipirona", "Dipirona sódica 500mg")
    assert substances_conflict("Amoxicilina", "Amoxicilina + Clavulanato")


def test_short_tokens_do_not_match_by_containment() -> None:
    # "AAS" is too short to wildcard-match; only equality counts
    assert not substances_conflict("AAS", "AASNE")
    assert substances_conflict("AAS", "aas")


def test_no_match_for_different_substances() -> None:
    assert not substances_conflict("Dipirona", "Paracetamol")
    assert not substances_conflict("Dipirona", "")
    assert not substances_conflict("", "Paracetamol")


def test_find_conflicts_only_for_active_allergies() -> None:
    allergies = [
        _allergy("Dipirona", status="active", reaction="Urticária", severity="severe"),
        _allergy("Penicilina", status="resolved"),
        _allergy("Látex", status="inactive"),
    ]
    conflicts = find_allergy_conflicts(allergies, ["Dipirona", "Penicilina"])
    assert len(conflicts) == 1
    only = conflicts[0]
    assert only.substance_display == "Dipirona"
    assert only.reaction == "Urticária"
    assert only.severity == "severe"
    assert only.matched_substance == "Dipirona"


def test_find_conflicts_empty_when_no_substances_or_no_match() -> None:
    allergies = [_allergy("Dipirona")]
    assert find_allergy_conflicts(allergies, []) == []
    assert find_allergy_conflicts(allergies, [None, ""]) == []
    assert find_allergy_conflicts(allergies, ["Paracetamol"]) == []


def test_find_conflicts_reports_each_active_allergy_once() -> None:
    allergies = [_allergy("Dipirona"), _allergy("Amoxicilina")]
    substances = ["Dipirona", "Amoxicilina potássica", "Paracetamol"]
    conflicts = find_allergy_conflicts(allergies, substances)
    assert {c.substance_display for c in conflicts} == {"Dipirona", "Amoxicilina"}
