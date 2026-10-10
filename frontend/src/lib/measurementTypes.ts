// Single source of truth for the vital signs a consultation or the measurements
// screen can record. `key` is a `Measurement.*` i18n key; `code` is the stable
// value persisted in the Observation row (never rename it — it is stored);
// `color` is the line colour used by the interactive history charts; `min`/`max`
// are the plausible bounds mirrored by the server-side validation (WS-4), used
// for the inline client-side warning.
export const MEASUREMENT_TYPES = [
  { code: "body-weight", key: "typeWeight", unit: "kg", color: "#0ea5e9", min: 0.5, max: 500 },
  { code: "body-height", key: "typeHeight", unit: "cm", color: "#8b5cf6", min: 20, max: 300 },
  { code: "blood-pressure-systolic", key: "typeBPSystolic", unit: "mmHg", color: "#ef4444", min: 40, max: 300 },
  { code: "blood-pressure-diastolic", key: "typeBPDiastolic", unit: "mmHg", color: "#f97316", min: 20, max: 200 },
  { code: "body-temperature", key: "typeTemperature", unit: "°C", color: "#f59e0b", min: 30, max: 45 },
  { code: "oxygen-saturation", key: "typeOxygenSaturation", unit: "%", color: "#06b6d4", min: 0, max: 100 },
  { code: "heart-rate", key: "typeHeartRate", unit: "bpm", color: "#ec4899", min: 20, max: 300 },
  { code: "respiratory-rate", key: "typeRespiratoryRate", unit: "/min", color: "#14b8a6", min: 5, max: 80 },
  { code: "capillary-glucose", key: "typeCapillaryGlucose", unit: "mg/dL", color: "#a855f7", min: 10, max: 1000 },
  { code: "pain-eva", key: "typePainEva", unit: "/10", color: "#f43f5e", min: 0, max: 10 },
  { code: "head-circumference", key: "typeHeadCircumference", unit: "cm", color: "#22c55e", min: 20, max: 70 },
  { code: "bmi", key: "typeBMI", unit: "kg/m²", color: "#10b981", min: 5, max: 200 },
] as const;

export type MeasurementTypeCode = (typeof MEASUREMENT_TYPES)[number]["code"];

export function measurementType(code: string) {
  return MEASUREMENT_TYPES.find((m) => m.code === code) ?? null;
}

/** Whether a value sits inside the plausible bounds for its vital (WS-4). */
export function isPlausible(code: string, value: number): boolean {
  const m = measurementType(code);
  if (!m || !Number.isFinite(value)) return true;
  return value >= m.min && value <= m.max;
}

/** BMI from weight (kg) and height (cm), rounded to 1 decimal — or null. */
export function computeBmi(weightKg?: number, heightCm?: number): number | null {
  if (!weightKg || !heightCm || heightCm <= 0) return null;
  const m = heightCm / 100;
  return Math.round((weightKg / (m * m)) * 10) / 10;
}
