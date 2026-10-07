// Single source of truth for the vital signs a consultation or the measurements
// screen can record. `key` is a `Measurement.*` i18n key; `code` is the stable
// value persisted in the Observation row (never rename it — it is stored);
// `color` is the line colour used by the interactive history charts.
export const MEASUREMENT_TYPES = [
  { code: "body-weight", key: "typeWeight", unit: "kg", color: "#0ea5e9" },
  { code: "body-height", key: "typeHeight", unit: "cm", color: "#8b5cf6" },
  { code: "blood-pressure-systolic", key: "typeBPSystolic", unit: "mmHg", color: "#ef4444" },
  { code: "blood-pressure-diastolic", key: "typeBPDiastolic", unit: "mmHg", color: "#f97316" },
  { code: "body-temperature", key: "typeTemperature", unit: "°C", color: "#f59e0b" },
  { code: "oxygen-saturation", key: "typeOxygenSaturation", unit: "%", color: "#06b6d4" },
  { code: "heart-rate", key: "typeHeartRate", unit: "bpm", color: "#ec4899" },
  { code: "bmi", key: "typeBMI", unit: "kg/m²", color: "#10b981" },
] as const;

export type MeasurementTypeCode = (typeof MEASUREMENT_TYPES)[number]["code"];

export function measurementType(code: string) {
  return MEASUREMENT_TYPES.find((m) => m.code === code) ?? null;
}

/** BMI from weight (kg) and height (cm), rounded to 1 decimal — or null. */
export function computeBmi(weightKg?: number, heightCm?: number): number | null {
  if (!weightKg || !heightCm || heightCm <= 0) return null;
  const m = heightCm / 100;
  return Math.round((weightKg / (m * m)) * 10) / 10;
}