"use client";

import { useTranslations } from "next-intl";
import {
  ADVERSE_EFFECTS,
  BIRTH_ATTENDANTS,
  BIRTH_POSITIONS,
  BLEEDING_ESTIMATION,
  BREASTFEEDING_DIFFICULTIES,
  CONDOM_USE,
  CONTRACEPTIVE_METHODS,
  DELIVERY_INTERCORRENCES,
  ELIGIBILITY_CONDITIONS,
  GENDER_IDENTITIES,
  GYNECOLOGICAL_COMPLAINTS,
  IDENTIFIED_NEEDS,
  MATERNAL_ELIMINATIONS,
  MATERNAL_FEEDING,
  MATERNAL_IMMUNIZATION,
  MENSTRUAL_CYCLES,
  MOTHER_NEWBORN_BOND,
  NON_PHARM_METHODS,
  PARTOGRAM_TYPES,
  PHARM_ANALGESIA,
  PLACENTA_MANAGEMENT,
  POSTPARTUM_ORIENTATIONS,
  PPH_CAUSES,
  REFERRALS,
  RETURN_SATISFACTION,
  SEXUAL_ORIENTATIONS,
  STI_TESTING,
  type NursingStructured,
  type TriBool,
} from "./fexeoNursingModel";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

// --- Small reusable controls (mirror FexeoFields, namespace "Nursing") ---

function Group({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-3 rounded-lg border p-3">
      <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</legend>
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
      {children}
    </fieldset>
  );
}

function TriBoolField({ label, value, onChange }: { label: string; value: TriBool; onChange: (v: TriBool) => void }) {
  const t = useTranslations("Nursing");
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <select
        value={value === null ? "" : value ? "true" : "false"}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "true")}
        className={inputCls}
      >
        <option value="">{t("Bool_not_informed")}</option>
        <option value="true">{t("Bool_yes")}</option>
        <option value="false">{t("Bool_no")}</option>
      </select>
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  prefix,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
  prefix: string;
}) {
  const t = useTranslations("Nursing");
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
        <option value="">{t("NotInformed")}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {t(`${prefix}${o}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input type="number" min={0} value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </label>
  );
}

function DateField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input type="date" value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </label>
  );
}

function ChecklistGroup({
  title,
  prefix,
  options,
  value,
  onChange,
}: {
  title: string;
  prefix: string;
  options: readonly string[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const t = useTranslations("Nursing");
  function toggle(key: string) {
    onChange(value.includes(key) ? value.filter((k) => k !== key) : [...value, key]);
  }
  return (
    <div className="space-y-1.5 text-sm">
      <span className="font-medium">{title}</span>
      <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
        {options.map((o) => (
          <label key={o} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={value.includes(o)}
              onChange={() => toggle(o)}
              className="size-4 rounded border-input"
            />
            {t(`${prefix}${o}`)}
          </label>
        ))}
      </div>
    </div>
  );
}

// --- Conditional subform by subcategory ---

export function NursingStructuredFields({
  subcategory,
  value,
  onChange,
}: {
  subcategory: string;
  value: NursingStructured;
  onChange: (patch: Partial<NursingStructured>) => void;
}) {
  const t = useTranslations("Nursing");
  const set = <K extends keyof NursingStructured>(k: K, v: NursingStructured[K]) =>
    onChange({ [k]: v } as Partial<NursingStructured>);

  if (subcategory === "labor") {
    return (
      <Group title={t("LaborSection")}>
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("RobsonClass")}
            value={value.robson_class}
            onChange={(v) => set("robson_class", v)}
            options={["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]}
            prefix="Robson_"
          />
          <SelectField
            label={t("BirthAttendant")}
            value={value.birth_attendant}
            onChange={(v) => set("birth_attendant", v)}
            options={BIRTH_ATTENDANTS}
            prefix="Attendant_"
          />
          <TriBoolField label={t("DoulaPresent")} value={value.doula_present} onChange={(v) => set("doula_present", v)} />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("PartogramType")}
            value={value.partogram_type}
            onChange={(v) => set("partogram_type", v)}
            options={PARTOGRAM_TYPES}
            prefix="Partogram_"
          />
          <TriBoolField label={t("Amniotomy")} value={value.amniotomy_done} onChange={(v) => set("amniotomy_done", v)} />
          <NumberField label={t("AmniotomyCm")} value={value.amniotomy_cm} onChange={(v) => set("amniotomy_cm", v)} />
        </div>

        <ChecklistGroup
          title={t("NonPharmMethods")}
          prefix="NPM_"
          options={NON_PHARM_METHODS}
          value={value.non_pharmacological_methods}
          onChange={(v) => set("non_pharmacological_methods", v)}
        />

        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("PharmacologicalAnalgesia")}
            value={value.pharmacological_analgesia}
            onChange={(v) => set("pharmacological_analgesia", v)}
            options={PHARM_ANALGESIA}
            prefix="Analgesia_"
          />
          <SelectField
            label={t("BirthPosition")}
            value={value.birth_position}
            onChange={(v) => set("birth_position", v)}
            options={BIRTH_POSITIONS}
            prefix="Position_"
          />
          <SelectField
            label={t("DeliveryIntercorrence")}
            value={value.delivery_intercorrence}
            onChange={(v) => set("delivery_intercorrence", v)}
            options={DELIVERY_INTERCORRENCES}
            prefix="DeliveryInt_"
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("PlacentaManagement")}
            value={value.placenta_management}
            onChange={(v) => set("placenta_management", v)}
            options={PLACENTA_MANAGEMENT}
            prefix="Placenta_"
          />
          <TriBoolField label={t("PinardGlobe")} value={value.pinard_globe} onChange={(v) => set("pinard_globe", v)} />
          <SelectField
            label={t("BleedingEstimation")}
            value={value.bleeding_estimation}
            onChange={(v) => set("bleeding_estimation", v)}
            options={BLEEDING_ESTIMATION}
            prefix="Bleeding_"
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <TriBoolField label={t("PphDiagnosis")} value={value.pph_diagnosis} onChange={(v) => set("pph_diagnosis", v)} />
          <SelectField
            label={t("PphCause")}
            value={value.pph_cause}
            onChange={(v) => set("pph_cause", v)}
            options={PPH_CAUSES}
            prefix="PphCause_"
          />
          <NumberField label={t("ShockIndex")} value={value.shock_index} onChange={(v) => set("shock_index", v)} />
        </div>
        <TextField label={t("Uterotonics")} value={value.uterotonics} onChange={(v) => set("uterotonics", v)} />
      </Group>
    );
  }

  if (subcategory === "postpartum") {
    return (
      <Group title={t("PostpartumSection")} note={t("PostpartumNote")}>
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("MaternalFeeding")}
            value={value.maternal_feeding}
            onChange={(v) => set("maternal_feeding", v)}
            options={MATERNAL_FEEDING}
            prefix="MatFeed_"
          />
          <SelectField
            label={t("MaternalEliminations")}
            value={value.maternal_eliminations}
            onChange={(v) => set("maternal_eliminations", v)}
            options={MATERNAL_ELIMINATIONS}
            prefix="MatElim_"
          />
          <SelectField
            label={t("MotherNewbornBond")}
            value={value.mother_newborn_bond}
            onChange={(v) => set("mother_newborn_bond", v)}
            options={MOTHER_NEWBORN_BOND}
            prefix="Bond_"
          />
        </div>
        <ChecklistGroup
          title={t("BreastfeedingDifficulty")}
          prefix="BFD_"
          options={BREASTFEEDING_DIFFICULTIES}
          value={value.breastfeeding_difficulty}
          onChange={(v) => set("breastfeeding_difficulty", v)}
        />
        <ChecklistGroup
          title={t("MaternalImmunization")}
          prefix="MatImm_"
          options={MATERNAL_IMMUNIZATION}
          value={value.immunization}
          onChange={(v) => set("immunization", v)}
        />
        <ChecklistGroup
          title={t("PostpartumOrientations")}
          prefix="PPO_"
          options={POSTPARTUM_ORIENTATIONS}
          value={value.orientations}
          onChange={(v) => set("orientations", v)}
        />
      </Group>
    );
  }

  if (subcategory === "sexual_reproductive") {
    return (
      <Group title={t("SexualSection")} note={t("SensitiveNote")}>
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField
            label={t("GenderIdentity")}
            value={value.gender_identity}
            onChange={(v) => set("gender_identity", v)}
            options={GENDER_IDENTITIES}
            prefix="Gender_"
          />
          <SelectField
            label={t("SexualOrientation")}
            value={value.sexual_orientation}
            onChange={(v) => set("sexual_orientation", v)}
            options={SEXUAL_ORIENTATIONS}
            prefix="Orientation_"
          />
          <SelectField
            label={t("MenstrualCycle")}
            value={value.cycle}
            onChange={(v) => set("cycle", v)}
            options={MENSTRUAL_CYCLES}
            prefix="Cycle_"
          />
          <NumberField label={t("MenarcheAge")} value={value.menarche_age} onChange={(v) => set("menarche_age", v)} />
          <DateField label={t("Dum")} value={value.dum} onChange={(v) => set("dum", v)} />
          <TextField
            label={t("FlowCharacteristics")}
            value={value.flow_characteristics}
            onChange={(v) => set("flow_characteristics", v)}
          />
        </div>
        <ChecklistGroup
          title={t("GynecologicalComplaints")}
          prefix="Gyn_"
          options={GYNECOLOGICAL_COMPLAINTS}
          value={value.gynecological_complaints}
          onChange={(v) => set("gynecological_complaints", v)}
        />
        <div className="grid gap-3 sm:grid-cols-3">
          <TriBoolField label={t("StiHistory")} value={value.sti_history} onChange={(v) => set("sti_history", v)} />
          <TextField label={t("StiWhich")} value={value.sti_which} onChange={(v) => set("sti_which", v)} />
          <TextField
            label={t("CytopathologyCurrent")}
            value={value.cytopathology_current}
            onChange={(v) => set("cytopathology_current", v)}
          />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <TriBoolField
            label={t("SexualPartners")}
            value={value.sexual_partners}
            onChange={(v) => set("sexual_partners", v)}
          />
          <SelectField
            label={t("CondomUse")}
            value={value.condom_use}
            onChange={(v) => set("condom_use", v)}
            options={CONDOM_USE}
            prefix="Condom_"
          />
          <SelectField
            label={t("CurrentContraceptive")}
            value={value.current_contraceptive}
            onChange={(v) => set("current_contraceptive", v)}
            options={CONTRACEPTIVE_METHODS}
            prefix="Method_"
          />
        </div>
        <SelectField
          label={t("DesiredContraceptive")}
          value={value.desired_contraceptive}
          onChange={(v) => set("desired_contraceptive", v)}
          options={CONTRACEPTIVE_METHODS}
          prefix="Method_"
        />
        <ChecklistGroup
          title={t("EligibilityConditions")}
          prefix="Elig_"
          options={ELIGIBILITY_CONDITIONS}
          value={value.eligibility_conditions}
          onChange={(v) => set("eligibility_conditions", v)}
        />
        <ChecklistGroup
          title={t("StiTesting")}
          prefix="Sti_"
          options={STI_TESTING}
          value={value.sti_testing}
          onChange={(v) => set("sti_testing", v)}
        />
        <ChecklistGroup
          title={t("IdentifiedNeeds")}
          prefix="Need_"
          options={IDENTIFIED_NEEDS}
          value={value.identified_needs}
          onChange={(v) => set("identified_needs", v)}
        />
        <ChecklistGroup
          title={t("Referrals")}
          prefix="Referral_"
          options={REFERRALS}
          value={value.referrals}
          onChange={(v) => set("referrals", v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <SelectField
            label={t("ReturnSatisfaction")}
            value={value.return_satisfaction}
            onChange={(v) => set("return_satisfaction", v)}
            options={RETURN_SATISFACTION}
            prefix="Satisfaction_"
          />
        </div>
        <ChecklistGroup
          title={t("AdverseEffects")}
          prefix="Adverse_"
          options={ADVERSE_EFFECTS}
          value={value.adverse_effects}
          onChange={(v) => set("adverse_effects", v)}
        />
      </Group>
    );
  }

  return null;
}
