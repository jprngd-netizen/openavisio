// NewbornRecord structured fields (FExEO-SUS I.2/I.3, R4 Fase 1 schema,
// Fase 2 UI) — the data model for the Recém-nascido section form.
//
// A NewbornRecord is 1:1 with a PregnancyOutcome (a live birth). Everything is
// optional: an empty control becomes an explicit `null` (or is omitted) in the
// payload, so the form is the single source of truth and a value can be cleared.
// Field names / enum values mirror `backend/app/schemas/newborn_record.py`.

// --- Controlled vocabularies ---

export const NEWBORN_SEXES = ["F", "M", "indeterminado"] as const;
export const DELIVERY_TYPES = ["vaginal", "abdominal", "forceps", "vacuo"] as const;
export const NEWBORN_CLASSIFICATIONS = ["AIG", "PIG", "GIG"] as const;
export const CORD_CLAMPINGS = ["lt_1min", "1_3min", "gt_3min"] as const;
export const FEEDINGS = [
  "leite_materno_livre_demanda",
  "ordenhado_pasteurizado",
  "formula_infantil",
  "mista",
  "leite_humano",
] as const;

// 1º exame físico — sistema por sistema.
export const EXAM_SYSTEMS = [
  "geral",
  "pele",
  "cabeca",
  "face",
  "olhos",
  "narinas",
  "orelhas",
  "boca",
  "pescoco_clavicula",
  "torax_respiratorio",
  "cardiovascular",
  "abdome",
  "genitalia",
  "anus",
  "dorso",
  "membros",
  "musculatura",
] as const;
export const EXAM_STATUSES = ["normal", "alterado", "nao_avaliado"] as const;

// Reflexos primitivos.
export const REFLEXES = ["succao", "busca", "preensao", "preensao_plantar", "moro", "marcha"] as const;
export const REFLEX_STATUSES = ["presente", "diminuido", "ausente"] as const;

// Eliminações (diurese, mecônio).
export const ELIMINATION_ITEMS = ["diurese", "meconio"] as const;
export const ELIMINATION_STATUSES = ["presente", "ausente", "alteracao"] as const;

// Imunização (BCG, HepB).
export const IMMUNIZATION_ITEMS = ["bcg", "hepatite_b"] as const;

// Reanimação neonatal (passos, medicações).
export const REANIMATION_STEPS = [
  "passos_iniciais",
  "cpap",
  "babypuff",
  "vpp",
  "o2_inalatorio",
  "massagem_cardiaca",
  "intubacao",
  "oximetro",
  "cateterismo_umbilical",
  "expansor_volume",
  "medicacoes",
] as const;

// --- Types ---

export type TriBool = boolean | null;
export type ExamEntry = { status: string; observacao: string };

export type NewbornForm = {
  birth_datetime: string;
  sex: string;
  delivery_type: string;
  gestational_age_weeks: string;
  classification: string;
  apgar_1: string;
  apgar_5: string;
  apgar_10: string;
  weight_g: string;
  length_cm: string;
  pc_cm: string;
  pt_cm: string;
  pa_cm: string;
  feeding: string;
  hypoglycemia: TriBool;
  hypothermia: TriBool;
  skin_to_skin_1h: TriBool;
  cord_clamping: string;
  congenital_malformation: TriBool;
  congenital_malformation_desc: string;
  notes: string;
  physical_exam: Record<string, ExamEntry>;
  reflexes: Record<string, string>;
  eliminations: Record<string, string>;
  immunization: Record<string, boolean>;
  reanimation: string[];
};

// --- Empty / seed factories ---

export function emptyNewbornForm(): NewbornForm {
  return {
    birth_datetime: "",
    sex: "",
    delivery_type: "",
    gestational_age_weeks: "",
    classification: "",
    apgar_1: "",
    apgar_5: "",
    apgar_10: "",
    weight_g: "",
    length_cm: "",
    pc_cm: "",
    pt_cm: "",
    pa_cm: "",
    feeding: "",
    hypoglycemia: null,
    hypothermia: null,
    skin_to_skin_1h: null,
    cord_clamping: "",
    congenital_malformation: null,
    congenital_malformation_desc: "",
    notes: "",
    physical_exam: Object.fromEntries(EXAM_SYSTEMS.map((k) => [k, { status: "", observacao: "" }])),
    reflexes: Object.fromEntries(REFLEXES.map((k) => [k, ""])),
    eliminations: Object.fromEntries(ELIMINATION_ITEMS.map((k) => [k, ""])),
    immunization: Object.fromEntries(IMMUNIZATION_ITEMS.map((k) => [k, false])),
    reanimation: [],
  };
}

// --- Normalisers ---

function str(x: unknown): string {
  return typeof x === "string" ? x : "";
}
function numStr(x: unknown): string {
  return typeof x === "number" ? String(x) : str(x);
}
function tri(x: unknown): TriBool {
  return x === true ? true : x === false ? false : null;
}

export function newbornFormFromRecord(record: any): NewbornForm {
  const pe = (record?.physical_exam ?? {}) as Record<string, any>;
  const rf = (record?.reflexes ?? {}) as Record<string, unknown>;
  const el = (record?.eliminations ?? {}) as Record<string, unknown>;
  const im = (record?.immunization ?? {}) as Record<string, unknown>;
  const cm = record?.congenital_malformation;
  const hasDesc = typeof cm === "string";
  return {
    birth_datetime: record?.birth_datetime ? String(record.birth_datetime).slice(0, 16) : "",
    sex: str(record?.sex),
    delivery_type: str(record?.delivery_type),
    gestational_age_weeks: numStr(record?.gestational_age_weeks),
    classification: str(record?.classification),
    apgar_1: numStr(record?.apgar_1),
    apgar_5: numStr(record?.apgar_5),
    apgar_10: numStr(record?.apgar_10),
    weight_g: numStr(record?.weight_g),
    length_cm: numStr(record?.length_cm),
    pc_cm: numStr(record?.pc_cm),
    pt_cm: numStr(record?.pt_cm),
    pa_cm: numStr(record?.pa_cm),
    feeding: str(record?.feeding),
    hypoglycemia: tri(record?.hypoglycemia),
    hypothermia: tri(record?.hypothermia),
    skin_to_skin_1h: tri(record?.skin_to_skin_1h),
    cord_clamping: str(record?.cord_clamping),
    congenital_malformation: hasDesc ? true : tri(cm),
    congenital_malformation_desc: hasDesc ? String(cm) : "",
    notes: str(record?.notes),
    physical_exam: Object.fromEntries(
      EXAM_SYSTEMS.map((k) => {
        const e = pe[k] ?? {};
        return [k, { status: str(e.status), observacao: str(e.observacao) }];
      }),
    ),
    reflexes: Object.fromEntries(REFLEXES.map((k) => [k, str(rf[k])])),
    eliminations: Object.fromEntries(ELIMINATION_ITEMS.map((k) => [k, str(el[k])])),
    immunization: Object.fromEntries(IMMUNIZATION_ITEMS.map((k) => [k, im[k] === true])),
    reanimation: Array.isArray(record?.reanimation) ? record.reanimation.map((x: unknown) => String(x)) : [],
  };
}

// --- Payload builder ---

export function newbornPayload(form: NewbornForm): Record<string, unknown> {
  const num = (s: string) => (s.trim() === "" ? null : Number(s));
  const t = (s: string) => (s.trim() === "" ? null : s.trim());

  const exam: Record<string, ExamEntry> = {};
  for (const k of EXAM_SYSTEMS) {
    const e = form.physical_exam[k];
    if (e && e.status) {
      exam[k] = e.observacao.trim() ? { status: e.status, observacao: e.observacao.trim() } : { status: e.status, observacao: "" };
    }
  }
  const reflexes: Record<string, string> = {};
  for (const k of REFLEXES) if (form.reflexes[k]) reflexes[k] = form.reflexes[k];

  const eliminations: Record<string, string> = {};
  for (const k of ELIMINATION_ITEMS) if (form.eliminations[k]) eliminations[k] = form.eliminations[k];

  const immunization = Object.fromEntries(IMMUNIZATION_ITEMS.map((k) => [k, form.immunization[k] === true]));
  const anyImmunization = IMMUNIZATION_ITEMS.some((k) => form.immunization[k] === true);

  let malformation: boolean | string | null = null;
  if (form.congenital_malformation === false) malformation = false;
  else if (form.congenital_malformation === true) {
    malformation = form.congenital_malformation_desc.trim() || true;
  }

  return {
    birth_datetime: form.birth_datetime || null,
    sex: form.sex || null,
    delivery_type: form.delivery_type || null,
    gestational_age_weeks: num(form.gestational_age_weeks),
    classification: form.classification || null,
    apgar_1: num(form.apgar_1),
    apgar_5: num(form.apgar_5),
    apgar_10: num(form.apgar_10),
    weight_g: num(form.weight_g),
    length_cm: num(form.length_cm),
    pc_cm: num(form.pc_cm),
    pt_cm: num(form.pt_cm),
    pa_cm: num(form.pa_cm),
    feeding: t(form.feeding),
    hypoglycemia: form.hypoglycemia,
    hypothermia: form.hypothermia,
    skin_to_skin_1h: form.skin_to_skin_1h,
    cord_clamping: t(form.cord_clamping),
    congenital_malformation: malformation,
    physical_exam: Object.keys(exam).length ? exam : null,
    reflexes: Object.keys(reflexes).length ? reflexes : null,
    eliminations: Object.keys(eliminations).length ? eliminations : null,
    immunization: anyImmunization || Object.keys(immunization).length ? immunization : null,
    reanimation: form.reanimation.length ? form.reanimation : null,
    notes: t(form.notes),
  };
}

export function listToChips(x: unknown): string[] {
  if (!Array.isArray(x)) return [];
  return x.map((it) => (it == null ? "" : String(it))).filter(Boolean);
}
