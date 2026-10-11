"use client";

import { useTranslations } from "next-intl";
import { listToChips } from "./fexeoNursingModel";

// Read-only projection of a nursing-care record's FExEO `structured_data`,
// rendered below the row. Only keys that were actually set are shown.

function safeLabel(t: (k: string) => string, key: string, fallback: string): string {
  try {
    return t(key);
  } catch {
    return fallback;
  }
}

function Row({ parts }: { parts: string[] }) {
  if (parts.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 border-t pt-2 text-xs text-muted-foreground">
      {parts.map((p, i) => (
        <span key={i}>{p}</span>
      ))}
    </div>
  );
}

const SCALAR_KEYS = new Set(["dum", "amniotomy_cm", "shock_index", "menarche_age"]);

export function NursingStructuredSummary({ record }: { record: any }) {
  const t = useTranslations("Nursing");
  const sub = record?.subcategory as string | undefined;
  const data = (record?.structured_data ?? null) as Record<string, unknown> | null;
  if (!data || typeof data !== "object" || !sub || sub === "general") return null;

  const parts: string[] = [];
  const tri = (v: unknown) => (v === true ? t("Bool_yes") : v === false ? t("Bool_no") : null);

  // Human labels per key, resolved through the field-label map below.
  const LABELS: Record<string, string> = {
    robson_class: t("RobsonClass"),
    birth_attendant: t("BirthAttendant"),
    doula_present: t("DoulaPresent"),
    partogram_type: t("PartogramType"),
    amniotomy_done: t("Amniotomy"),
    amniotomy_cm: t("AmniotomyCm"),
    non_pharmacological_methods: t("NonPharmMethods"),
    pharmacological_analgesia: t("PharmacologicalAnalgesia"),
    birth_position: t("BirthPosition"),
    delivery_intercorrence: t("DeliveryIntercorrence"),
    placenta_management: t("PlacentaManagement"),
    pinard_globe: t("PinardGlobe"),
    bleeding_estimation: t("BleedingEstimation"),
    pph_diagnosis: t("PphDiagnosis"),
    pph_cause: t("PphCause"),
    shock_index: t("ShockIndex"),
    uterotonics: t("Uterotonics"),
    maternal_feeding: t("MaternalFeeding"),
    maternal_eliminations: t("MaternalEliminations"),
    breastfeeding_difficulty: t("BreastfeedingDifficulty"),
    mother_newborn_bond: t("MotherNewbornBond"),
    immunization: t("MaternalImmunization"),
    orientations: t("PostpartumOrientations"),
    gender_identity: t("GenderIdentity"),
    sexual_orientation: t("SexualOrientation"),
    menarche_age: t("MenarcheAge"),
    cycle: t("MenstrualCycle"),
    dum: t("Dum"),
    flow_characteristics: t("FlowCharacteristics"),
    gynecological_complaints: t("GynecologicalComplaints"),
    sti_history: t("StiHistory"),
    sti_which: t("StiWhich"),
    cytopathology_current: t("CytopathologyCurrent"),
    sexual_partners: t("SexualPartners"),
    condom_use: t("CondomUse"),
    current_contraceptive: t("CurrentContraceptive"),
    desired_contraceptive: t("DesiredContraceptive"),
    eligibility_conditions: t("EligibilityConditions"),
    sti_testing: t("StiTesting"),
    identified_needs: t("IdentifiedNeeds"),
    referrals: t("Referrals"),
    return_satisfaction: t("ReturnSatisfaction"),
    adverse_effects: t("AdverseEffects"),
  };

  // Prefix per key so enum values resolve to their translated label.
  const PREFIX: Record<string, string> = {
    robson_class: "Robson_",
    birth_attendant: "Attendant_",
    partogram_type: "Partogram_",
    pharmacological_analgesia: "Analgesia_",
    birth_position: "Position_",
    delivery_intercorrence: "DeliveryInt_",
    placenta_management: "Placenta_",
    bleeding_estimation: "Bleeding_",
    pph_cause: "PphCause_",
    maternal_feeding: "MatFeed_",
    maternal_eliminations: "MatElim_",
    mother_newborn_bond: "Bond_",
    gender_identity: "Gender_",
    sexual_orientation: "Orientation_",
    cycle: "Cycle_",
    condom_use: "Condom_",
    current_contraceptive: "Method_",
    desired_contraceptive: "Method_",
    return_satisfaction: "Satisfaction_",
  };
  const LIST_PREFIX: Record<string, string> = {
    non_pharmacological_methods: "NPM_",
    breastfeeding_difficulty: "BFD_",
    immunization: "MatImm_",
    orientations: "PPO_",
    gynecological_complaints: "Gyn_",
    eligibility_conditions: "Elig_",
    sti_testing: "Sti_",
    identified_needs: "Need_",
    referrals: "Referral_",
    adverse_effects: "Adverse_",
  };

  for (const [key, raw] of Object.entries(data)) {
    const label = LABELS[key] ?? key;
    if (LIST_PREFIX[key]) {
      const items = listToChips(raw);
      if (items.length) {
        parts.push(`${label}: ${items.map((k) => safeLabel(t, `${LIST_PREFIX[key]}${k}`, k)).join(", ")}`);
      }
      continue;
    }
    if (PREFIX[key]) {
      const s = String(raw);
      parts.push(`${label}: ${safeLabel(t, `${PREFIX[key]}${s}`, s)}`);
      continue;
    }
    if (SCALAR_KEYS.has(key)) {
      parts.push(`${label}: ${String(raw)}`);
      continue;
    }
    const b = tri(raw);
    if (b) parts.push(`${label}: ${b}`);
    else if (typeof raw === "string" && raw) parts.push(`${label}: ${raw}`);
  }

  // A contraceptive method value that lives in the shared vocabulary is already
  // prefixed above; nothing else to do.

  return <Row parts={parts} />;
}
