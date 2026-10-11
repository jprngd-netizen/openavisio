// FExEO-SUS structured fields for Enfermagem (R4 Fase 1 schema, Fase 2 UI) —
// the data model for the nursing-care `subcategory` / `instrument_type` /
// `structured_data` (JSON) that differentiate the four acompanhamento
// instruments charted as nursing care (I.2 labor, I.3 postpartum, I.4 sexual
// and reproductive health, plus the general note).
//
// Everything here is optional: an empty control becomes an explicit `null` (or
// is omitted) in the payload, so the form is the single source of truth and a
// value can be cleared, not only set. Field names and enum values mirror the
// backend (`backend/app/models/nursing_care.py`) and the FExEO caderno digest.
//
// Sensitive fields (gender identity, sexual orientation, violence) are handled
// discreetly and always offer an explicit "prefere não informar" option.

// --- Controlled vocabularies ---

export const SUBCATEGORIES = ["labor", "postpartum", "sexual_reproductive", "general"] as const;

// I.2 — labor
export const BIRTH_ATTENDANTS = ["enfermeira", "obstetriz", "medico", "parteira", "doula", "outro"] as const;
export const PARTOGRAM_TYPES = ["linha_alerta_acao", "oms", "nao_preenchido"] as const;
export const NON_PHARM_METHODS = [
  "banheira",
  "chuveiro",
  "acupuntura",
  "massagem",
  "respiracao_consciente",
  "aromaterapia",
  "pontos_de_pressao",
  "musicoterapia",
  "penumbra",
  "cromoterapia",
  "cavalinho",
  "escada_ling",
  "bola",
  "deambulacao",
  "danca",
  "mudanca_de_posicao",
  "alongamento",
  "outro",
] as const;
export const PHARM_ANALGESIA = ["nenhuma", "peridural", "raqui", "combinada"] as const;
export const BIRTH_POSITIONS = [
  "deitada",
  "semi_deitada",
  "banqueta",
  "cocoras",
  "lateralizada",
  "quatro_apoios",
  "em_pe",
] as const;
export const DELIVERY_INTERCORRENCES = [
  "sem_intercorrencias",
  "distocia_ombro",
  "retencao_placentaria",
  "hemorragia",
  "prolapso_cordao",
  "iminencia_eclampsia",
  "outra",
] as const;
export const PLACENTA_MANAGEMENT = ["ativo", "passivo"] as const;
export const BLEEDING_ESTIMATION = ["visual", "quantitativa", "na"] as const;
export const PPH_CAUSES = ["tonus", "trauma", "tecido", "trombina"] as const;

// I.3 — postpartum (mother)
export const MATERNAL_FEEDING = ["livre_demanda", "dieta_livre", "jejum", "outro"] as const;
export const MATERNAL_ELIMINATIONS = ["espontanea", "dificuldade", "alteracao", "na"] as const;
export const BREASTFEEDING_DIFFICULTIES = [
  "pega_inadequada",
  "ingurgitamento",
  "fissura_mamilar",
  "bico_plano",
  "bico_invertido",
  "producao_insuficiente",
  "dor",
  "mastite",
  "uso_de_chupeta",
  "uso_de_mamadeira",
  "orientacao_insuficiente",
  "outro",
] as const;
export const MOTHER_NEWBORN_BOND = ["adequado", "inadequado", "na"] as const;
export const MATERNAL_IMMUNIZATION = ["bcg", "hepatite_b", "outra"] as const;
export const POSTPARTUM_ORIENTATIONS = [
  "amamentacao",
  "higiene_intima",
  "planejamento_reprodutivo",
  "cuidados_rn",
  "revisao_parto_abstinencia",
  "outro",
] as const;

// I.4 — sexual and reproductive health
export const GENDER_IDENTITIES = [
  "mulher_cis",
  "homem_transgenero",
  "nao_binaria",
  "outra",
  "prefere_nao_informar",
] as const;
export const SEXUAL_ORIENTATIONS = [
  "heterossexual",
  "lesbica",
  "gay",
  "bissexual",
  "pansexual",
  "assexual",
  "outra",
  "prefere_nao_informar",
] as const;
export const MENSTRUAL_CYCLES = ["regular", "irregular", "amenorreia", "menopausa"] as const;
export const GYNECOLOGICAL_COMPLAINTS = [
  "dor_pelvica",
  "corrimento",
  "sangramento_anormal",
  "colica",
  "alteracao_menstrual",
  "prurido_ardor",
  "dispareunia",
  "ausencia",
  "outra",
] as const;
export const CONDOM_USE = ["sempre", "as_vezes", "nunca"] as const;
export const CONTRACEPTIVE_METHODS = [
  "anticoncepcional_oral",
  "injetavel_mensal",
  "injetavel_trimestral",
  "implante",
  "diu_cobre",
  "diu_hormonal",
  "preservativo_feminino",
  "preservativo_masculino",
  "laqueadura",
  "vasectomia",
  "coito_interrompido",
  "tabela_calendario",
  "sintotermico",
  "outro",
] as const;
export const ELIGIBILITY_CONDITIONS = [
  "has",
  "tabagismo",
  "enxaqueca_com_aura",
  "tromboembolismo_previo",
  "diabetes",
  "cancer_de_mama",
  "lactacao",
  "outra",
] as const;
export const STI_TESTING = ["hepatite_b", "hepatite_c", "sifilis", "hiv"] as const;
export const IDENTIFIED_NEEDS = [
  "escolha_ou_revisao_de_metodo",
  "retirada_de_diu",
  "retirada_de_implante",
  "desejo_de_gestacao",
  "prevencao_de_ist",
  "tratamento_vulvovaginite",
  "tratamento_cervicite",
  "tratamento_de_ist",
  "dificuldade_de_acesso",
  "apoio_psicossocial",
  "vulnerabilidade_social",
  "violencia_sexual",
  "violencia_domestica",
  "encaminhamento_multiprofissional",
  "outra",
] as const;
export const REFERRALS = [
  "aps",
  "ginecologia",
  "planejamento_reprodutivo",
  "psicologia",
  "servico_social",
  "rede_de_protecao",
  "atencao_violencias",
  "infectologia",
  "outro",
] as const;
export const RETURN_SATISFACTION = ["muito_satisfeito", "satisfeito", "insatisfeito", "na"] as const;
export const ADVERSE_EFFECTS = [
  "sangramento",
  "cefaleia",
  "nausea",
  "ganho_de_peso",
  "alteracao_humor",
  "diminuicao_libido",
  "acne",
  "mastalgia",
  "outro",
] as const;

// --- Types ---

export type TriBool = boolean | null;

export type LaborData = {
  robson_class: string;
  birth_attendant: string;
  doula_present: TriBool;
  partogram_type: string;
  amniotomy_done: TriBool;
  amniotomy_cm: string;
  non_pharmacological_methods: string[];
  pharmacological_analgesia: string;
  birth_position: string;
  delivery_intercorrence: string;
  placenta_management: string;
  pinard_globe: TriBool;
  bleeding_estimation: string;
  pph_diagnosis: TriBool;
  pph_cause: string;
  shock_index: string;
  uterotonics: string;
};

export type PostpartumData = {
  maternal_feeding: string;
  maternal_eliminations: string;
  breastfeeding_difficulty: string[];
  mother_newborn_bond: string;
  immunization: string[];
  orientations: string[];
};

export type SexualReproductiveData = {
  gender_identity: string;
  sexual_orientation: string;
  menarche_age: string;
  cycle: string;
  dum: string;
  flow_characteristics: string;
  gynecological_complaints: string[];
  sti_history: TriBool;
  sti_which: string;
  cytopathology_current: string;
  sexual_partners: TriBool;
  condom_use: string;
  current_contraceptive: string;
  desired_contraceptive: string;
  eligibility_conditions: string[];
  sti_testing: string[];
  identified_needs: string[];
  referrals: string[];
  return_satisfaction: string;
  adverse_effects: string[];
};

export type NursingStructured = LaborData & PostpartumData & SexualReproductiveData;

// --- Empty / seed factories ---

export function emptyLaborData(): LaborData {
  return {
    robson_class: "",
    birth_attendant: "",
    doula_present: null,
    partogram_type: "",
    amniotomy_done: null,
    amniotomy_cm: "",
    non_pharmacological_methods: [],
    pharmacological_analgesia: "",
    birth_position: "",
    delivery_intercorrence: "",
    placenta_management: "",
    pinard_globe: null,
    bleeding_estimation: "",
    pph_diagnosis: null,
    pph_cause: "",
    shock_index: "",
    uterotonics: "",
  };
}

export function emptyPostpartumData(): PostpartumData {
  return {
    maternal_feeding: "",
    maternal_eliminations: "",
    breastfeeding_difficulty: [],
    mother_newborn_bond: "",
    immunization: [],
    orientations: [],
  };
}

export function emptySexualReproductiveData(): SexualReproductiveData {
  return {
    gender_identity: "",
    sexual_orientation: "",
    menarche_age: "",
    cycle: "",
    dum: "",
    flow_characteristics: "",
    gynecological_complaints: [],
    sti_history: null,
    sti_which: "",
    cytopathology_current: "",
    sexual_partners: null,
    condom_use: "",
    current_contraceptive: "",
    desired_contraceptive: "",
    eligibility_conditions: [],
    sti_testing: [],
    identified_needs: [],
    referrals: [],
    return_satisfaction: "",
    adverse_effects: [],
  };
}

export function emptyNursingStructured(): NursingStructured {
  return { ...emptyLaborData(), ...emptyPostpartumData(), ...emptySexualReproductiveData() };
}

// --- Normalisers ---

function chips(x: unknown): string[] {
  if (!Array.isArray(x)) return [];
  return x.map((it) => (it == null ? "" : String(it))).filter(Boolean);
}
function str(x: unknown): string {
  return typeof x === "string" ? x : "";
}
function numStr(x: unknown): string {
  return typeof x === "number" ? String(x) : str(x);
}
function tri(x: unknown): TriBool {
  return x === true ? true : x === false ? false : null;
}

export function nursingStructuredFromRecord(record: any): NursingStructured {
  const d = (record?.structured_data ?? {}) as Record<string, unknown>;
  const labor = emptyLaborData();
  const post = emptyPostpartumData();
  const sexual = emptySexualReproductiveData();
  return {
    ...labor,
    ...post,
    ...sexual,

    robson_class: str(d.robson_class),
    birth_attendant: str(d.birth_attendant),
    doula_present: tri(d.doula_present),
    partogram_type: str(d.partogram_type),
    amniotomy_done: tri(d.amniotomy_done),
    amniotomy_cm: numStr(d.amniotomy_cm),
    non_pharmacological_methods: chips(d.non_pharmacological_methods),
    pharmacological_analgesia: str(d.pharmacological_analgesia),
    birth_position: str(d.birth_position),
    delivery_intercorrence: str(d.delivery_intercorrence),
    placenta_management: str(d.placenta_management),
    pinard_globe: tri(d.pinard_globe),
    bleeding_estimation: str(d.bleeding_estimation),
    pph_diagnosis: tri(d.pph_diagnosis),
    pph_cause: str(d.pph_cause),
    shock_index: numStr(d.shock_index),
    uterotonics: str(d.uterotonics),

    maternal_feeding: str(d.maternal_feeding),
    maternal_eliminations: str(d.maternal_eliminations),
    breastfeeding_difficulty: chips(d.breastfeeding_difficulty),
    mother_newborn_bond: str(d.mother_newborn_bond),
    immunization: chips(d.immunization),
    orientations: chips(d.orientations),

    gender_identity: str(d.gender_identity),
    sexual_orientation: str(d.sexual_orientation),
    menarche_age: numStr(d.menarche_age),
    cycle: str(d.cycle),
    dum: str(d.dum),
    flow_characteristics: str(d.flow_characteristics),
    gynecological_complaints: chips(d.gynecological_complaints),
    sti_history: tri(d.sti_history),
    sti_which: str(d.sti_which),
    cytopathology_current: str(d.cytopathology_current),
    sexual_partners: tri(d.sexual_partners),
    condom_use: str(d.condom_use),
    current_contraceptive: str(d.current_contraceptive),
    desired_contraceptive: str(d.desired_contraceptive),
    eligibility_conditions: chips(d.eligibility_conditions),
    sti_testing: chips(d.sti_testing),
    identified_needs: chips(d.identified_needs),
    referrals: chips(d.referrals),
    return_satisfaction: str(d.return_satisfaction),
    adverse_effects: chips(d.adverse_effects),
  };
}

// --- Payload builder — only the fields of the current subcategory are sent, so
// switching subcategory does not silently persist another instrument's data.

export function nursingStructuredPayload(
  subcategory: string,
  ext: NursingStructured,
): Record<string, unknown> | null {
  const t = (s: string) => (s.trim() === "" ? null : s.trim());
  const tn = (s: string) => (s.trim() === "" ? null : Number(s));
  const list = (a: string[]) => (a.length ? a : null);

  let out: Record<string, unknown> = {};
  if (subcategory === "labor") {
    out = {
      robson_class: t(ext.robson_class),
      birth_attendant: t(ext.birth_attendant),
      doula_present: ext.doula_present,
      partogram_type: t(ext.partogram_type),
      amniotomy_done: ext.amniotomy_done,
      amniotomy_cm: tn(ext.amniotomy_cm),
      non_pharmacological_methods: list(ext.non_pharmacological_methods),
      pharmacological_analgesia: t(ext.pharmacological_analgesia),
      birth_position: t(ext.birth_position),
      delivery_intercorrence: t(ext.delivery_intercorrence),
      placenta_management: t(ext.placenta_management),
      pinard_globe: ext.pinard_globe,
      bleeding_estimation: t(ext.bleeding_estimation),
      pph_diagnosis: ext.pph_diagnosis,
      pph_cause: t(ext.pph_cause),
      shock_index: tn(ext.shock_index),
      uterotonics: t(ext.uterotonics),
    };
  } else if (subcategory === "postpartum") {
    out = {
      maternal_feeding: t(ext.maternal_feeding),
      maternal_eliminations: t(ext.maternal_eliminations),
      breastfeeding_difficulty: list(ext.breastfeeding_difficulty),
      mother_newborn_bond: t(ext.mother_newborn_bond),
      immunization: list(ext.immunization),
      orientations: list(ext.orientations),
    };
  } else if (subcategory === "sexual_reproductive") {
    out = {
      gender_identity: t(ext.gender_identity),
      sexual_orientation: t(ext.sexual_orientation),
      menarche_age: tn(ext.menarche_age),
      cycle: t(ext.cycle),
      dum: t(ext.dum),
      flow_characteristics: t(ext.flow_characteristics),
      gynecological_complaints: list(ext.gynecological_complaints),
      sti_history: ext.sti_history,
      sti_which: t(ext.sti_which),
      cytopathology_current: t(ext.cytopathology_current),
      sexual_partners: ext.sexual_partners,
      condom_use: t(ext.condom_use),
      current_contraceptive: t(ext.current_contraceptive),
      desired_contraceptive: t(ext.desired_contraceptive),
      eligibility_conditions: list(ext.eligibility_conditions),
      sti_testing: list(ext.sti_testing),
      identified_needs: list(ext.identified_needs),
      referrals: list(ext.referrals),
      return_satisfaction: t(ext.return_satisfaction),
      adverse_effects: list(ext.adverse_effects),
    };
  } else {
    return null;
  }
  // Drop keys that carry no information so the stored JSON stays minimal.
  const cleaned = Object.fromEntries(Object.entries(out).filter(([, v]) => v !== null));
  return Object.keys(cleaned).length ? cleaned : null;
}

export function listToChips(x: unknown): string[] {
  return chips(x);
}
