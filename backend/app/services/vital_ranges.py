"""Plausibility ranges for vital-sign measurements (WS-4).

A single source of truth for the server-side range check applied to vitals
recorded through the encounter and the observation endpoints. The bounds are
deliberately generous physiological limits: their job is to catch typos and
unit mix-ups (a blood pressure of ``3000``, a temperature of ``400``), not to
substitute clinical judgement. The client mirrors the same bounds for a
friendly inline warning (see ``frontend/src/lib/measurementTypes.ts``).

Unknown codes (lab analytes, free text) are ignored — this guard is for vitals
only and must never reject a lab result.
"""

# code -> (min, max, unit)
VITAL_RANGES: dict[str, tuple[float, float, str]] = {
    "body-weight": (0.5, 500, "kg"),
    "body-height": (20, 300, "cm"),
    "blood-pressure-systolic": (40, 300, "mmHg"),
    "blood-pressure-diastolic": (20, 200, "mmHg"),
    "body-temperature": (30, 45, "°C"),
    "oxygen-saturation": (0, 100, "%"),
    "heart-rate": (20, 300, "bpm"),
    "bmi": (5, 200, "kg/m²"),
    "respiratory-rate": (5, 80, "/min"),
    "capillary-glucose": (10, 1000, "mg/dL"),
    "pain-eva": (0, 10, "0-10"),
    "head-circumference": (20, 70, "cm"),
}


def vital_range(code: str | None) -> tuple[float, float, str] | None:
    """The plausible ``(min, max, unit)`` for a vital code, or ``None``."""
    return VITAL_RANGES.get(code) if code else None


def check_vital(code: str | None, value: float | None) -> None:
    """Raise ``ValueError`` when a vital value is outside its plausible range.

    No-op for ``None`` values and for codes that are not known vitals (lab
    analytes and free-text parameters are allowed through untouched).
    """
    if value is None:
        return
    rng = vital_range(code)
    if rng is None:
        return
    lo, hi, unit = rng
    if not (lo <= value <= hi):
        raise ValueError(
            f"{code}: {value} {unit} fora da faixa plausível ({lo}–{hi} {unit})"
        )
