"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { X, Plus } from "lucide-react";
import {
  CONSULTATION_TYPES,
  EDEMA_CLASSES,
  EDEMA_CLASS_KEY,
  FAMILY_HISTORY_ITEMS,
  IMC_CLASSES,
  MAIN_CARE_PROVIDERS,
  PHYSICAL_EXAM_ITEMS,
  PREECLAMPSIA_HIGH_RISK,
  PREECLAMPSIA_MODERATE_RISK,
  RISK_CLASSES,
  VACCINES_IN_GESTATION,
  VACCINATION_STATUS_ITEMS,
  VACCINATION_STATUS_VALUES,
  type PregnancyExtended,
  type TriBool,
  type VisitExtended,
} from "./fexeoModel";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

// --- Small reusable controls (reuse the page's existing field styling) ---

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <details className="rounded-xl border bg-muted/20 p-3">
      <summary className="cursor-pointer select-none text-sm font-semibold">{title}</summary>
      {note && <p className="mt-2 text-xs text-muted-foreground">{note}</p>}
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  );
}

function TriBoolField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: TriBool;
  onChange: (v: TriBool) => void;
}) {
  const t = useTranslations("Pregnancy");
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
  labelFor,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
  labelFor: (v: string) => string;
}) {
  const t = useTranslations("Pregnancy");
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
        <option value="">{t("NoDate")}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {labelFor(o)}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  max,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  max?: number;
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input
        type="number"
        min={0}
        max={max}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputCls}
      />
    </label>
  );
}

function ChipListEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const t = useTranslations("Pregnancy");
  const [draft, setDraft] = useState("");

  function add() {
    const v = draft.trim();
    if (!v) return;
    if (!value.includes(v)) onChange([...value, v]);
    setDraft("");
  }

  return (
    <div className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {value.length === 0 ? (
          <span className="text-xs text-muted-foreground">{t("ChipsEmpty")}</span>
        ) : (
          value.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-0.5 text-xs"
            >
              {v}
              <button
                type="button"
                aria-label={t("Delete")}
                onClick={() => onChange(value.filter((x) => x !== v))}
                className="text-destructive hover:opacity-70"
              >
                <X className="size-3" />
              </button>
            </span>
          ))
        )}
      </div>
      <div className="flex items-center gap-2">
        <input
          value={draft}
          placeholder={t("ChipsPlaceholder")}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          className={inputCls}
        />
        <button
          type="button"
          onClick={add}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
        >
          <Plus className="size-3.5" />
          {t("Add")}
        </button>
      </div>
    </div>
  );
}

function ChecklistGroup({
  title,
  labelPrefix,
  options,
  value,
  onChange,
}: {
  title: string;
  labelPrefix: string;
  options: readonly string[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const t = useTranslations("Pregnancy");
  function toggle(key: string) {
    onChange(value.includes(key) ? value.filter((k) => k !== key) : [...value, key]);
  }
  return (
    <div className="space-y-1.5 text-sm">
      <span className="font-medium">{title}</span>
      <div className="grid gap-1 sm:grid-cols-2">
        {options.map((o) => (
          <label key={o} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={value.includes(o)}
              onChange={() => toggle(o)}
              className="size-4 rounded border-input"
            />
            {t(`${labelPrefix}${o}`)}
          </label>
        ))}
      </div>
    </div>
  );
}

// --- Gestação (Pregnancy) extended fields ---

export function PregnancyExtendedFields({
  value,
  onChange,
}: {
  value: PregnancyExtended;
  onChange: (patch: Partial<PregnancyExtended>) => void;
}) {
  const t = useTranslations("Pregnancy");
  const set = <K extends keyof PregnancyExtended>(k: K, v: PregnancyExtended[K]) =>
    onChange({ [k]: v } as Partial<PregnancyExtended>);

  return (
    <Section title={t("RiskSection")}>
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField
          label={t("RiskClassification")}
          value={value.risk_classification}
          onChange={(v) => set("risk_classification", v)}
          options={RISK_CLASSES}
          labelFor={(v) => t(`Risk_${v}`)}
        />
        <TriBoolField
          label={t("PlannedPregnancy")}
          value={value.planned_pregnancy}
          onChange={(v) => set("planned_pregnancy", v)}
        />
        <TextField
          label={t("ContraceptiveAtConception")}
          value={value.contraceptive_at_conception}
          onChange={(v) => set("contraceptive_at_conception", v)}
        />
      </div>

      <div>
        <span className="text-sm font-medium">{t("ObstetricHistory")}</span>
        <div className="mt-1.5 grid gap-3 sm:grid-cols-5">
          <NumberField label={t("GravidaCount")} value={value.gravida} onChange={(v) => set("gravida", v)} />
          <NumberField
            label={t("ParaVaginal")}
            value={value.para_vaginal}
            onChange={(v) => set("para_vaginal", v)}
          />
          <NumberField
            label={t("ParaCesarean")}
            value={value.para_cesarean}
            onChange={(v) => set("para_cesarean", v)}
          />
          <NumberField
            label={t("AbortionsCount")}
            value={value.abortions}
            onChange={(v) => set("abortions", v)}
          />
          <NumberField
            label={t("LivingChildren")}
            value={value.living_children}
            onChange={(v) => set("living_children", v)}
          />
        </div>
      </div>

      <SelectField
        label={t("ImcPreGestational")}
        value={value.imc_pre_gestational_class}
        onChange={(v) => set("imc_pre_gestational_class", v)}
        options={IMC_CLASSES}
        labelFor={(v) => t(`Imc_${v}`)}
      />

      <fieldset className="space-y-3 rounded-lg border p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("PreeclampsiaRisk")}
        </legend>
        <ChecklistGroup
          title={t("PreeclampsiaHigh")}
          labelPrefix="PEF_"
          options={PREECLAMPSIA_HIGH_RISK}
          value={value.preeclampsia_risk_factors}
          onChange={(v) => set("preeclampsia_risk_factors", v)}
        />
        <ChecklistGroup
          title={t("PreeclampsiaModerate")}
          labelPrefix="PEM_"
          options={PREECLAMPSIA_MODERATE_RISK}
          value={value.preeclampsia_moderate_risk_factors}
          onChange={(v) => set("preeclampsia_moderate_risk_factors", v)}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <TriBoolField
            label={t("AspirinProphylaxis")}
            value={value.aspirin_prophylaxis}
            onChange={(v) => set("aspirin_prophylaxis", v)}
          />
          <NumberField
            label={t("AspirinStartWeek")}
            value={value.aspirin_start_week}
            onChange={(v) => set("aspirin_start_week", v)}
            max={42}
          />
        </div>
      </fieldset>

      {/* Sensitive data — discreet block, blank by default. */}
      <fieldset className="space-y-3 rounded-lg border border-dashed bg-muted/30 p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("PerinatalMentalHealth")} / {t("DomesticViolence")}
        </legend>
        <p className="text-xs text-muted-foreground">{t("SensitiveNote")}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <TriBoolField
            label={t("PerinatalMentalHealth")}
            value={value.perinatal_mental_health_history}
            onChange={(v) => set("perinatal_mental_health_history", v)}
          />
          <TriBoolField
            label={t("DomesticViolence")}
            value={value.domestic_violence_investigated}
            onChange={(v) => set("domestic_violence_investigated", v)}
          />
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-lg border p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("FamilyHistory")}
        </legend>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {FAMILY_HISTORY_ITEMS.map((k) => (
            <label key={k} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={value.family_history[k]}
                onChange={(e) =>
                  set("family_history", { ...value.family_history, [k]: e.target.checked })
                }
                className="size-4 rounded border-input"
              />
              {t(`FH_${k}`)}
            </label>
          ))}
        </div>
        <TextField
          label={t("FH_outros")}
          value={value.family_history.outros}
          onChange={(v) => set("family_history", { ...value.family_history, outros: v })}
        />
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label={t("ReferenceMaternity")}
          value={value.reference_maternity}
          onChange={(v) => set("reference_maternity", v)}
        />
        <TriBoolField
          label={t("LinkedToMaternity")}
          value={value.linked_to_maternity}
          onChange={(v) => set("linked_to_maternity", v)}
        />
      </div>
    </Section>
  );
}

// --- Pré-natal (PregnancyVisit) extended fields ---

export function VisitExtendedFields({
  value,
  onChange,
}: {
  value: VisitExtended;
  onChange: (patch: Partial<VisitExtended>) => void;
}) {
  const t = useTranslations("Pregnancy");
  const set = <K extends keyof VisitExtended>(k: K, v: VisitExtended[K]) =>
    onChange({ [k]: v } as Partial<VisitExtended>);

  function toggleVaccine(k: string, on: boolean) {
    set("vaccines_in_gestation", { ...value.vaccines_in_gestation, [k]: on });
  }
  function setVaxStatus(k: string, v: string) {
    set("vaccination_status", { ...value.vaccination_status, [k]: v });
  }
  function toggleExam(k: string, field: "avaliado" | "alteracao", on: boolean) {
    const cur = value.physical_exam[k] ?? { avaliado: false, alteracao: false };
    const next = { ...cur, [field]: on };
    if (field === "avaliado" && !on) next.alteracao = false;
    set("physical_exam", { ...value.physical_exam, [k]: next });
  }

  return (
    <Section title={t("VisitSection")}>
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField
          label={t("ConsultationType")}
          value={value.consultation_type}
          onChange={(v) => set("consultation_type", v)}
          options={CONSULTATION_TYPES}
          labelFor={(v) => t(`Consult_${v}`)}
        />
        <SelectField
          label={t("MainCareProvider")}
          value={value.main_care_provider}
          onChange={(v) => set("main_care_provider", v)}
          options={MAIN_CARE_PROVIDERS}
          labelFor={(v) => t(`Provider_${v}`)}
        />
        <SelectField
          label={t("EdemaClass")}
          value={value.edema_class}
          onChange={(v) => set("edema_class", v)}
          options={EDEMA_CLASSES}
          labelFor={(v) => t(`EdemaClass_${EDEMA_CLASS_KEY[v] ?? "ausente"}`)}
        />
        <TriBoolField
          label={t("FirstVisitBefore12w")}
          value={value.first_visit_before_12w}
          onChange={(v) => set("first_visit_before_12w", v)}
        />
        <TriBoolField
          label={t("RemoteConsult")}
          value={value.remote_consult}
          onChange={(v) => set("remote_consult", v)}
        />
        <TriBoolField
          label={t("DentalHealthActivity")}
          value={value.dental_health_activity}
          onChange={(v) => set("dental_health_activity", v)}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <ChipListEditor
          label={t("Complaints")}
          value={value.complaints}
          onChange={(v) => set("complaints", v)}
        />
        <ChipListEditor
          label={t("WarningSigns")}
          value={value.warning_signs}
          onChange={(v) => set("warning_signs", v)}
        />
        <ChipListEditor
          label={t("CurrentIntercurrences")}
          value={value.current_intercurrences}
          onChange={(v) => set("current_intercurrences", v)}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <TriBoolField
          label={t("LeopoldDone")}
          value={value.leopold_done}
          onChange={(v) => set("leopold_done", v)}
        />
        <TriBoolField
          label={t("FundalHeightOnChart")}
          value={value.fundal_height_recorded_on_chart}
          onChange={(v) => set("fundal_height_recorded_on_chart", v)}
        />
        <TriBoolField
          label={t("BcfChange")}
          value={value.bcf_change}
          onChange={(v) => set("bcf_change", v)}
        />
      </div>

      <fieldset className="space-y-2 rounded-lg border p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("PhysicalExam")}
        </legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {PHYSICAL_EXAM_ITEMS.map((k) => {
            const e = value.physical_exam[k] ?? { avaliado: false, alteracao: false };
            return (
              <div
                key={k}
                className="flex items-center justify-between gap-3 rounded-md border bg-background px-2.5 py-1.5"
              >
                <span className="text-sm">{t(`PhysicalExam_${k}`)}</span>
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-1.5 text-xs">
                    <input
                      type="checkbox"
                      checked={e.avaliado}
                      onChange={(ev) => toggleExam(k, "avaliado", ev.target.checked)}
                      className="size-4 rounded border-input"
                    />
                    {t("ExamAssessed")}
                  </label>
                  <label className="flex items-center gap-1.5 text-xs">
                    <input
                      type="checkbox"
                      checked={e.alteracao}
                      disabled={!e.avaliado}
                      onChange={(ev) => toggleExam(k, "alteracao", ev.target.checked)}
                      className="size-4 rounded border-input disabled:opacity-40"
                    />
                    {t("ExamAlteration")}
                  </label>
                </div>
              </div>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="space-y-3 rounded-lg border p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("Vaccination")}
        </legend>
        <div>
          <span className="text-sm font-medium">{t("VaccinationStatus")}</span>
          <div className="mt-1.5 grid gap-3 sm:grid-cols-3">
            {VACCINATION_STATUS_ITEMS.map((k) => (
              <label key={k} className="space-y-1.5 text-sm">
                <span className="font-medium">{t(`VaccinationStatus_${k}`)}</span>
                <select
                  value={value.vaccination_status[k] ?? ""}
                  onChange={(e) => setVaxStatus(k, e.target.value)}
                  className={inputCls}
                >
                  <option value="">{t("Bool_not_informed")}</option>
                  {VACCINATION_STATUS_VALUES.map((v) => (
                    <option key={v} value={v}>
                      {t(`VS_${v}`)}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </div>
        <div>
          <span className="text-sm font-medium">{t("VaccinesInGestation")}</span>
          <div className="mt-1.5 flex flex-wrap gap-x-6 gap-y-2">
            {VACCINES_IN_GESTATION.map((k) => (
              <label key={k} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={value.vaccines_in_gestation[k] === true}
                  onChange={(e) => toggleVaccine(k, e.target.checked)}
                  className="size-4 rounded border-input"
                />
                {t(`Vac_${k}`)}
              </label>
            ))}
          </div>
        </div>
      </fieldset>

      <ChipListEditor
        label={t("OrientationTopics")}
        value={value.orientation_topics}
        onChange={(v) => set("orientation_topics", v)}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <TriBoolField
          label={t("WeightGainWeeklyOk")}
          value={value.weight_gain_weekly_ok}
          onChange={(v) => set("weight_gain_weekly_ok", v)}
        />
        <TriBoolField
          label={t("BirthPlanElaborated")}
          value={value.birth_plan_elaborated}
          onChange={(v) => set("birth_plan_elaborated", v)}
        />
      </div>
    </Section>
  );
}
