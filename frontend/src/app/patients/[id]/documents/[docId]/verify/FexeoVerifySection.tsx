"use client";

import { useTranslations } from "next-intl";

// FExEO-SUS (R4 Fase 3) — the obstetric-nursing instruments the classifier
// recognises. The AI proposes an optional ``fexeo`` object in the extraction;
// this screen lets the nurse confirm each sub-object before it is written.
export const FEXEO_CLINICAL = new Set<string>([
  "fexeo_prenatal_monitoring",
  "fexeo_labor_birth_record",
  "fexeo_postpartum_rooming_record",
  "fexeo_sexual_reproductive_visit",
]);
export const FEXEO_COMPETENCY = "fexeo_competency_assessment";

// Display order of the sub-objects a clinical instrument may carry. Each maps
// to a card title; only sub-objects actually present in the extraction render.
export const FEXEO_SUBOBJECTS = [
  "pregnancy",
  "prenatal_visit",
  "nursing_care",
  "newborn",
  "outcome",
] as const;
export type FexeoSub = (typeof FEXEO_SUBOBJECTS)[number];

const CARD_TITLE: Record<string, string> = {
  pregnancy: "CardGestation",
  prenatal_visit: "CardPrenatalVisit",
  nursing_care: "CardNursing",
  newborn: "CardNewborn",
  outcome: "CardOutcome",
};

// Human label per known field key → i18n key. An unknown key (OCR is a
// suggestion) falls back to the de-underscored field name, never a raw crash.
const FIELD_LABEL: Record<string, string> = {
  lmp_date: "f_lmp_date",
  estimated_due_date: "f_estimated_due_date",
  ultrasound_due_date: "f_ultrasound_due_date",
  ultrasound_date: "f_ultrasound_date",
  ended_at: "f_ended_at",
  notes: "f_notes",
  risk_classification: "f_risk_classification",
  planned_pregnancy: "f_planned_pregnancy",
  contraceptive_at_conception: "f_contraceptive_at_conception",
  gravida: "f_gravida",
  para_vaginal: "f_para_vaginal",
  para_cesarean: "f_para_cesarean",
  abortions: "f_abortions",
  living_children: "f_living_children",
  preeclampsia_risk_factors: "f_preeclampsia_risk_factors",
  preeclampsia_moderate_risk_factors: "f_preeclampsia_moderate_risk_factors",
  aspirin_prophylaxis: "f_aspirin_prophylaxis",
  aspirin_start_week: "f_aspirin_start_week",
  imc_pre_gestational_class: "f_imc_pre_gestational_class",
  perinatal_mental_health_history: "f_perinatal_mental_health_history",
  domestic_violence_investigated: "f_domestic_violence_investigated",
  family_history: "f_family_history",
  reference_maternity: "f_reference_maternity",
  linked_to_maternity: "f_linked_to_maternity",

  visit_date: "f_visit_date",
  fundal_height_cm: "f_fundal_height_cm",
  fetal_heart_rate_bpm: "f_fetal_heart_rate_bpm",
  presentation: "f_presentation",
  edema: "f_edema",
  proteinuria: "f_proteinuria",
  consultation_type: "f_consultation_type",
  first_visit_before_12w: "f_first_visit_before_12w",
  main_care_provider: "f_main_care_provider",
  remote_consult: "f_remote_consult",
  dental_health_activity: "f_dental_health_activity",
  complaints: "f_complaints",
  warning_signs: "f_warning_signs",
  current_intercurrences: "f_current_intercurrences",
  edema_class: "f_edema_class",
  leopold_done: "f_leopold_done",
  fundal_height_recorded_on_chart: "f_fundal_height_recorded_on_chart",
  bcf_change: "f_bcf_change",
  physical_exam: "f_physical_exam",
  vaccination_status: "f_vaccination_status",
  vaccines_in_gestation: "f_vaccines_in_gestation",
  orientation_topics: "f_orientation_topics",
  weight_gain_weekly_ok: "f_weight_gain_weekly_ok",
  birth_plan_elaborated: "f_birth_plan_elaborated",

  occurred_at: "f_occurred_at",
  category: "f_category",
  performed_by: "f_performed_by",
  subcategory: "f_subcategory",
  instrument_type: "f_instrument_type",
  structured_data: "f_structured_data",

  outcome_type: "f_outcome_type",
  outcome_date: "f_outcome_date",
  newborn_weight_g: "f_newborn_weight_g",
  newborn_sex: "f_newborn_sex",

  birth_datetime: "f_birth_datetime",
  sex: "f_sex",
  delivery_type: "f_delivery_type",
  gestational_age_weeks: "f_gestational_age_weeks",
  classification: "f_classification",
  apgar_1: "f_apgar_1",
  apgar_5: "f_apgar_5",
  apgar_10: "f_apgar_10",
  weight_g: "f_weight_g",
  length_cm: "f_length_cm",
  pc_cm: "f_pc_cm",
  pt_cm: "f_pt_cm",
  pa_cm: "f_pa_cm",
  reflexes: "f_reflexes",
  feeding: "f_feeding",
  eliminations: "f_eliminations",
  hypoglycemia: "f_hypoglycemia",
  hypothermia: "f_hypothermia",
  immunization: "f_immunization",
  congenital_malformation: "f_congenital_malformation",
  reanimation: "f_reanimation",
  skin_to_skin_1h: "f_skin_to_skin_1h",
  cord_clamping: "f_cord_clamping",
};

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim() === "";
  if (Array.isArray(value)) return value.filter((v) => !isEmptyValue(v)).length === 0;
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).filter(([, v]) => !isEmptyValue(v)).length === 0;
  }
  return false;
}

/** Drop keys whose value is empty, recursively — only what the document states
 *  is ever sent back to the verify endpoint. */
export function pruneEmpty(obj: unknown): unknown {
  if (Array.isArray(obj)) {
    return obj.filter((v) => !isEmptyValue(v)).map((v) => pruneEmpty(v));
  }
  if (obj !== null && typeof obj === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      if (isEmptyValue(value)) continue;
      out[key] = pruneEmpty(value);
    }
    return out;
  }
  return obj;
}

/** De-underscore an unknown key into a readable name (OCR-sourced keys are not
 *  guaranteed to be in the label map). */
function prettify(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function FieldValue({ value }: { value: unknown }) {
  const t = useTranslations("FexeoVerify");

  if (typeof value === "boolean") return <>{value ? t("BoolYes") : t("BoolNo")}</>;
  if (Array.isArray(value)) {
    return (
      <>
        {value
          .filter((v) => !isEmptyValue(v))
          .map((v) => (typeof v === "object" ? JSON.stringify(v) : String(v)))
          .join(", ")}
      </>
    );
  }
  if (value !== null && typeof value === "object") {
    return (
      <span className="block space-y-1">
        {Object.entries(value as Record<string, unknown>)
          .filter(([, v]) => !isEmptyValue(v))
          .map(([k, v]) => (
            <span key={k} className="block">
              <span className="text-muted-foreground">{prettify(k)}: </span>
              {typeof v === "boolean" ? (v ? t("BoolYes") : t("BoolNo")) : typeof v === "object" ? JSON.stringify(v) : String(v)}
            </span>
          ))}
      </span>
    );
  }
  return <>{String(value)}</>;
}

function FieldRow({ name, value }: { name: string; value: unknown }) {
  const t = useTranslations("FexeoVerify");
  const label = FIELD_LABEL[name] ? t(FIELD_LABEL[name]) : prettify(name);
  return (
    <div className="flex flex-wrap gap-x-2 text-sm">
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">
        <FieldValue value={value} />
      </span>
    </div>
  );
}

function FexeoCard({
  sub,
  data,
  checked,
  onToggle,
}: {
  sub: string;
  data: Record<string, unknown>;
  checked: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("FexeoVerify");
  const fields = Object.entries(data).filter(([, v]) => !isEmptyValue(v));
  return (
    <div className={`rounded-lg border p-4 transition-opacity ${!checked ? "opacity-50" : ""}`}>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-4 w-4 rounded border-input accent-primary shrink-0"
        />
        <span className="text-sm font-semibold">{t(CARD_TITLE[sub])}</span>
        <span className="text-xs text-muted-foreground">{t("Include")}</span>
      </label>
      <div className="mt-3 space-y-1.5">
        {fields.map(([name, value]) => (
          <FieldRow key={name} name={name} value={value} />
        ))}
      </div>
    </div>
  );
}

/** The FExEO confirmation block: one card per sub-object present in the
 *  extraction, each with an "include" checkbox (default checked). */
export function FexeoVerifySection({
  fexeo,
  selected,
  onToggle,
}: {
  fexeo: Record<string, unknown>;
  selected: Set<string>;
  onToggle: (sub: string) => void;
}) {
  const t = useTranslations("FexeoVerify");
  const present = FEXEO_SUBOBJECTS.filter((sub) => {
    const value = fexeo[sub];
    return value !== null && typeof value === "object" && !isEmptyValue(value);
  });
  if (present.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card p-5">
      <h2 className="font-semibold">{t("Title")}</h2>
      <p className="mt-0.5 mb-4 text-xs text-muted-foreground">{t("Hint")}</p>
      <div className="space-y-3">
        {present.map((sub) => (
          <FexeoCard
            key={sub}
            sub={sub}
            data={fexeo[sub] as Record<string, unknown>}
            checked={selected.has(sub)}
            onToggle={() => onToggle(sub)}
          />
        ))}
      </div>
    </div>
  );
}

/** Formative (Parte II) instruments teach — they must never seed the chart. */
export function FexeoFormativeNotice() {
  const t = useTranslations("FexeoVerify");
  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-5">
      <h2 className="font-semibold text-amber-700 dark:text-amber-300">{t("FormativeTitle")}</h2>
      <p className="mt-1 text-sm text-amber-700/90 dark:text-amber-300/90">{t("FormativeNotice")}</p>
    </div>
  );
}