// FExEO-SUS structured fields (R4 Fase 1 schema, Fase 2 UI) — the data model
// for the Gestação (`Pregnancy`) and Pré-natal (`PregnancyVisit`) forms.
//
// Everything here is optional: an empty control becomes an explicit `null` in
// the payload, so the form is the single source of truth and a value can be
// cleared (not only set). Field names and enum values mirror the backend
// schemas verbatim (`backend/app/schemas/pregnancy.py`).

// --- Controlled vocabularies — mirror the backend StrEnums verbatim. ---

export const RISK_CLASSES = ["habitual", "intermediario", "alto"] as const;
export const IMC_CLASSES = ["baixo_peso", "adequado", "sobrepeso", "obesidade"] as const;
export const CONSULTATION_TYPES = ["primeira", "subsequente"] as const;
export const MAIN_CARE_PROVIDERS = ["enfermeiro", "medico", "obstetriz", "parteira", "outro"] as const;
export const EDEMA_CLASSES = ["ausente", "+", "++", "+++", "++++"] as const;
// Edema values contain "+", which is unusable as an i18n key suffix — map to keys.
export const EDEMA_CLASS_KEY: Record<string, string> = {
  ausente: "ausente",
  "+": "plus1",
  "++": "plus2",
  "+++": "plus3",
  "++++": "plus4",
};

export const PREECLAMPSIA_HIGH_RISK = [
  "hipertensao_cronica",
  "diabetes_pregestacional",
  "doenca_renal_cronica",
  "doenca_autoimune",
  "sindrome_antifosfolipide",
  "preeclampsia_previa",
  "gestacao_multipla",
  "obesidade",
  "tecnologia_reproducao_assistida",
] as const;

export const PREECLAMPSIA_MODERATE_RISK = [
  "nuliparidade",
  "idade_maior_35",
  "historia_familiar_preeclampsia",
  "intervalo_interpartal_maior_10a",
  "condicao_socioeconomica_desfavoravel",
] as const;

export const PHYSICAL_EXAM_ITEMS = [
  "pele_mucosas",
  "tireoide",
  "mamas",
  "ausculta_cardiaca",
  "ausculta_pulmonar",
] as const;

export const VACCINES_IN_GESTATION = ["dTpa", "dT", "VSR", "covid", "influenza"] as const;
export const VACCINATION_STATUS_ITEMS = ["hepatite_b", "antitetanica", "triplice_viral"] as const;
export const VACCINATION_STATUS_VALUES = ["completo", "incompleto"] as const;
export const FAMILY_HISTORY_ITEMS = ["diabetes", "hipertensao", "gemelar"] as const;

// --- Types ---

export type TriBool = boolean | null;
export type PhysicalExamEntry = { avaliado: boolean; alteracao: boolean };
export type FamilyHistory = {
  diabetes: boolean;
  hipertensao: boolean;
  gemelar: boolean;
  outros: string;
};

export type PregnancyExtended = {
  risk_classification: string;
  planned_pregnancy: TriBool;
  contraceptive_at_conception: string;
  gravida: string;
  para_vaginal: string;
  para_cesarean: string;
  abortions: string;
  living_children: string;
  preeclampsia_risk_factors: string[];
  preeclampsia_moderate_risk_factors: string[];
  aspirin_prophylaxis: TriBool;
  aspirin_start_week: string;
  imc_pre_gestational_class: string;
  perinatal_mental_health_history: TriBool;
  domestic_violence_investigated: TriBool;
  family_history: FamilyHistory;
  reference_maternity: string;
  linked_to_maternity: TriBool;
};

export type VisitExtended = {
  consultation_type: string;
  first_visit_before_12w: TriBool;
  main_care_provider: string;
  remote_consult: TriBool;
  dental_health_activity: TriBool;
  complaints: string[];
  warning_signs: string[];
  current_intercurrences: string[];
  edema_class: string;
  leopold_done: TriBool;
  fundal_height_recorded_on_chart: TriBool;
  bcf_change: TriBool;
  physical_exam: Record<string, PhysicalExamEntry>;
  vaccination_status: Record<string, string>;
  vaccines_in_gestation: Record<string, boolean>;
  orientation_topics: string[];
  weight_gain_weekly_ok: TriBool;
  birth_plan_elaborated: TriBool;
};

// --- Empty / seed factories ---

export function emptyPregnancyExtended(): PregnancyExtended {
  return {
    risk_classification: "",
    planned_pregnancy: null,
    contraceptive_at_conception: "",
    gravida: "",
    para_vaginal: "",
    para_cesarean: "",
    abortions: "",
    living_children: "",
    preeclampsia_risk_factors: [],
    preeclampsia_moderate_risk_factors: [],
    aspirin_prophylaxis: null,
    aspirin_start_week: "",
    imc_pre_gestational_class: "",
    perinatal_mental_health_history: null,
    domestic_violence_investigated: null,
    family_history: { diabetes: false, hipertensao: false, gemelar: false, outros: "" },
    reference_maternity: "",
    linked_to_maternity: null,
  };
}

function chips(x: unknown): string[] {
  if (!Array.isArray(x)) return [];
  return x
    .map((it) => {
      if (typeof it === "string") return it;
      if (it && typeof it === "object") {
        const o = it as Record<string, unknown>;
        const code = typeof o.code === "string" ? o.code : "";
        const display = typeof o.display === "string" ? o.display : "";
        return [code, display].filter(Boolean).join(" ");
      }
      return it == null ? "" : String(it);
    })
    .filter(Boolean);
}

function numToStr(x: unknown): string {
  return typeof x === "number" ? String(x) : "";
}

export function pregnancyExtendedFromEpisode(ep: any): PregnancyExtended {
  const fh = (ep?.family_history ?? {}) as Record<string, unknown>;
  return {
    risk_classification: ep?.risk_classification ?? "",
    planned_pregnancy: ep?.planned_pregnancy ?? null,
    contraceptive_at_conception: ep?.contraceptive_at_conception ?? "",
    gravida: numToStr(ep?.gravida),
    para_vaginal: numToStr(ep?.para_vaginal),
    para_cesarean: numToStr(ep?.para_cesarean),
    abortions: numToStr(ep?.abortions),
    living_children: numToStr(ep?.living_children),
    preeclampsia_risk_factors: chips(ep?.preeclampsia_risk_factors),
    preeclampsia_moderate_risk_factors: chips(ep?.preeclampsia_moderate_risk_factors),
    aspirin_prophylaxis: ep?.aspirin_prophylaxis ?? null,
    aspirin_start_week: numToStr(ep?.aspirin_start_week),
    imc_pre_gestational_class: ep?.imc_pre_gestational_class ?? "",
    perinatal_mental_health_history: ep?.perinatal_mental_health_history ?? null,
    domestic_violence_investigated: ep?.domestic_violence_investigated ?? null,
    family_history: {
      diabetes: fh.diabetes === true,
      hipertensao: fh.hipertensao === true,
      gemelar: fh.gemelar === true,
      outros: typeof fh.outros === "string" ? fh.outros : "",
    },
    reference_maternity: ep?.reference_maternity ?? "",
    linked_to_maternity: ep?.linked_to_maternity ?? null,
  };
}

export function emptyVisitExtended(): VisitExtended {
  return {
    consultation_type: "",
    first_visit_before_12w: null,
    main_care_provider: "",
    remote_consult: null,
    dental_health_activity: null,
    complaints: [],
    warning_signs: [],
    current_intercurrences: [],
    edema_class: "",
    leopold_done: null,
    fundal_height_recorded_on_chart: null,
    bcf_change: null,
    physical_exam: Object.fromEntries(
      PHYSICAL_EXAM_ITEMS.map((k) => [k, { avaliado: false, alteracao: false }]),
    ),
    vaccination_status: Object.fromEntries(VACCINATION_STATUS_ITEMS.map((k) => [k, ""])),
    vaccines_in_gestation: Object.fromEntries(VACCINES_IN_GESTATION.map((k) => [k, false])),
    orientation_topics: [],
    weight_gain_weekly_ok: null,
    birth_plan_elaborated: null,
  };
}

export function visitExtendedFromVisit(v: any): VisitExtended {
  const pe = (v?.physical_exam ?? {}) as Record<string, any>;
  const vs = (v?.vaccination_status ?? {}) as Record<string, unknown>;
  const vg = (v?.vaccines_in_gestation ?? {}) as Record<string, unknown>;
  return {
    consultation_type: v?.consultation_type ?? "",
    first_visit_before_12w: v?.first_visit_before_12w ?? null,
    main_care_provider: v?.main_care_provider ?? "",
    remote_consult: v?.remote_consult ?? null,
    dental_health_activity: v?.dental_health_activity ?? null,
    complaints: chips(v?.complaints),
    warning_signs: chips(v?.warning_signs),
    current_intercurrences: chips(v?.current_intercurrences),
    edema_class: v?.edema_class ?? "",
    leopold_done: v?.leopold_done ?? null,
    fundal_height_recorded_on_chart: v?.fundal_height_recorded_on_chart ?? null,
    bcf_change: v?.bcf_change ?? null,
    physical_exam: Object.fromEntries(
      PHYSICAL_EXAM_ITEMS.map((k) => {
        const e = pe[k] ?? {};
        return [k, { avaliado: !!e.avaliado, alteracao: !!e.alteracao }];
      }),
    ),
    vaccination_status: Object.fromEntries(
      VACCINATION_STATUS_ITEMS.map((k) => [k, typeof vs[k] === "string" ? (vs[k] as string) : ""]),
    ),
    vaccines_in_gestation: Object.fromEntries(VACCINES_IN_GESTATION.map((k) => [k, vg[k] === true])),
    orientation_topics: chips(v?.orientation_topics),
    weight_gain_weekly_ok: v?.weight_gain_weekly_ok ?? null,
    birth_plan_elaborated: v?.birth_plan_elaborated ?? null,
  };
}

// --- Payload builders — every key is sent (null when empty) so a value can be
// cleared, not only set. PATCH uses `exclude_unset`, so an explicit null sticks.

export function pregnancyExtendedPayload(ext: PregnancyExtended): Record<string, unknown> {
  const num = (s: string) => (s.trim() === "" ? null : Number(s));
  const fh = ext.family_history;
  const hasFH = fh.diabetes || fh.hipertensao || fh.gemelar || fh.outros.trim() !== "";
  return {
    risk_classification: ext.risk_classification || null,
    planned_pregnancy: ext.planned_pregnancy,
    contraceptive_at_conception: ext.contraceptive_at_conception.trim() || null,
    gravida: num(ext.gravida),
    para_vaginal: num(ext.para_vaginal),
    para_cesarean: num(ext.para_cesarean),
    abortions: num(ext.abortions),
    living_children: num(ext.living_children),
    preeclampsia_risk_factors: ext.preeclampsia_risk_factors.length
      ? ext.preeclampsia_risk_factors
      : null,
    preeclampsia_moderate_risk_factors: ext.preeclampsia_moderate_risk_factors.length
      ? ext.preeclampsia_moderate_risk_factors
      : null,
    aspirin_prophylaxis: ext.aspirin_prophylaxis,
    aspirin_start_week: num(ext.aspirin_start_week),
    imc_pre_gestational_class: ext.imc_pre_gestational_class || null,
    perinatal_mental_health_history: ext.perinatal_mental_health_history,
    domestic_violence_investigated: ext.domestic_violence_investigated,
    family_history: hasFH
      ? {
          diabetes: fh.diabetes,
          hipertensao: fh.hipertensao,
          gemelar: fh.gemelar,
          ...(fh.outros.trim() ? { outros: fh.outros.trim() } : {}),
        }
      : null,
    reference_maternity: ext.reference_maternity.trim() || null,
    linked_to_maternity: ext.linked_to_maternity,
  };
}

export function visitExtendedPayload(ext: VisitExtended): Record<string, unknown> {
  const examEntries = Object.entries(ext.physical_exam).filter(([, e]) => e.avaliado);
  const physical_exam = examEntries.length
    ? Object.fromEntries(examEntries.map(([k, e]) => [k, { avaliado: true, alteracao: e.alteracao }]))
    : null;

  const vax = Object.fromEntries(
    Object.entries(ext.vaccination_status).filter(([, v]) => v.trim() !== ""),
  );
  const vaccination_status = Object.keys(vax).length ? vax : null;

  const received = VACCINES_IN_GESTATION.filter((k) => ext.vaccines_in_gestation[k]);
  const vaccines_in_gestation = received.length
    ? Object.fromEntries(VACCINES_IN_GESTATION.map((k) => [k, ext.vaccines_in_gestation[k] === true]))
    : null;

  return {
    consultation_type: ext.consultation_type || null,
    first_visit_before_12w: ext.first_visit_before_12w,
    main_care_provider: ext.main_care_provider || null,
    remote_consult: ext.remote_consult,
    dental_health_activity: ext.dental_health_activity,
    complaints: ext.complaints.length ? ext.complaints : null,
    warning_signs: ext.warning_signs.length ? ext.warning_signs : null,
    current_intercurrences: ext.current_intercurrences.length ? ext.current_intercurrences : null,
    edema_class: ext.edema_class || null,
    leopold_done: ext.leopold_done,
    fundal_height_recorded_on_chart: ext.fundal_height_recorded_on_chart,
    bcf_change: ext.bcf_change,
    physical_exam,
    vaccination_status,
    vaccines_in_gestation,
    orientation_topics: ext.orientation_topics.length ? ext.orientation_topics : null,
    weight_gain_weekly_ok: ext.weight_gain_weekly_ok,
    birth_plan_elaborated: ext.birth_plan_elaborated,
  };
}

// Re-exported so summary components can normalise a raw backend list the same way.
export function listToChips(x: unknown): string[] {
  return chips(x);
}
