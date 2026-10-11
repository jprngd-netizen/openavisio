"use client";

import { useTranslations } from "next-intl";
import {
  CORD_CLAMPINGS,
  DELIVERY_TYPES,
  ELIMINATION_ITEMS,
  ELIMINATION_STATUSES,
  EXAM_STATUSES,
  EXAM_SYSTEMS,
  FEEDINGS,
  IMMUNIZATION_ITEMS,
  NEWBORN_CLASSIFICATIONS,
  NEWBORN_SEXES,
  REANIMATION_STEPS,
  REFLEX_STATUSES,
  REFLEXES,
  type NewbornForm,
  type TriBool,
} from "./newbornModel";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

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
  const t = useTranslations("Newborn");
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
  const t = useTranslations("Newborn");
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

function NumberField({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  step?: string;
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <input type="number" min={0} step={step} value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} />
    </label>
  );
}

export function NewbornFields({
  value,
  onChange,
}: {
  value: NewbornForm;
  onChange: (patch: Partial<NewbornForm>) => void;
}) {
  const t = useTranslations("Newborn");
  const set = <K extends keyof NewbornForm>(k: K, v: NewbornForm[K]) => onChange({ [k]: v } as Partial<NewbornForm>);

  function setExam(k: string, patch: Partial<{ status: string; observacao: string }>) {
    const cur = value.physical_exam[k] ?? { status: "", observacao: "" };
    set("physical_exam", { ...value.physical_exam, [k]: { ...cur, ...patch } });
  }
  function toggleReanim(o: string) {
    set("reanimation", value.reanimation.includes(o) ? value.reanimation.filter((x) => x !== o) : [...value.reanimation, o]);
  }

  return (
    <div className="space-y-3">
      <Group title={t("BirthSection")}>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="space-y-1.5 text-sm">
            <span className="font-medium">{t("BirthDateTime")}</span>
            <input
              type="datetime-local"
              value={value.birth_datetime}
              onChange={(e) => set("birth_datetime", e.target.value)}
              className={inputCls}
            />
          </label>
          <SelectField label={t("Sex")} value={value.sex} onChange={(v) => set("sex", v)} options={NEWBORN_SEXES} prefix="Sex_" />
          <SelectField
            label={t("DeliveryType")}
            value={value.delivery_type}
            onChange={(v) => set("delivery_type", v)}
            options={DELIVERY_TYPES}
            prefix="Delivery_"
          />
          <NumberField
            label={t("GestationalAgeWeeks")}
            value={value.gestational_age_weeks}
            onChange={(v) => set("gestational_age_weeks", v)}
            step="0.1"
          />
          <SelectField
            label={t("Classification")}
            value={value.classification}
            onChange={(v) => set("classification", v)}
            options={NEWBORN_CLASSIFICATIONS}
            prefix="Class_"
          />
          <SelectField
            label={t("CordClamping")}
            value={value.cord_clamping}
            onChange={(v) => set("cord_clamping", v)}
            options={CORD_CLAMPINGS}
            prefix="Cord_"
          />
        </div>
      </Group>

      <Group title={t("ApgarAnthro")}>
        <div className="grid gap-3 sm:grid-cols-4">
          <NumberField label={t("Apgar1")} value={value.apgar_1} onChange={(v) => set("apgar_1", v)} />
          <NumberField label={t("Apgar5")} value={value.apgar_5} onChange={(v) => set("apgar_5", v)} />
          <NumberField label={t("Apgar10")} value={value.apgar_10} onChange={(v) => set("apgar_10", v)} />
          <NumberField label={t("WeightG")} value={value.weight_g} onChange={(v) => set("weight_g", v)} />
        </div>
        <div className="grid gap-3 sm:grid-cols-4">
          <NumberField label={t("LengthCm")} value={value.length_cm} onChange={(v) => set("length_cm", v)} step="0.1" />
          <NumberField label={t("PcCm")} value={value.pc_cm} onChange={(v) => set("pc_cm", v)} step="0.1" />
          <NumberField label={t("PtCm")} value={value.pt_cm} onChange={(v) => set("pt_cm", v)} step="0.1" />
          <NumberField label={t("PaCm")} value={value.pa_cm} onChange={(v) => set("pa_cm", v)} step="0.1" />
        </div>
      </Group>

      <Group title={t("PhysicalExam")}>
        <div className="grid gap-2 sm:grid-cols-2">
          {EXAM_SYSTEMS.map((k) => {
            const e = value.physical_exam[k] ?? { status: "", observacao: "" };
            return (
              <div key={k} className="rounded-md border bg-background p-2.5">
                <span className="text-sm font-medium">{t(`System_${k}`)}</span>
                <div className="mt-1.5 flex items-center gap-2">
                  <select
                    value={e.status}
                    onChange={(ev) => setExam(k, { status: ev.target.value })}
                    className={inputCls}
                  >
                    <option value="">{t("NotInformed")}</option>
                    {EXAM_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {t(`ExamStatus_${s}`)}
                      </option>
                    ))}
                  </select>
                  <input
                    value={e.observacao}
                    onChange={(ev) => setExam(k, { observacao: ev.target.value })}
                    placeholder={t("Observation")}
                    className={inputCls}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Group>

      <Group title={t("Reflexes")}>
        <div className="grid gap-3 sm:grid-cols-3">
          {REFLEXES.map((k) => (
            <label key={k} className="space-y-1.5 text-sm">
              <span className="font-medium">{t(`Reflex_${k}`)}</span>
              <select
                value={value.reflexes[k] ?? ""}
                onChange={(e) => set("reflexes", { ...value.reflexes, [k]: e.target.value })}
                className={inputCls}
              >
                <option value="">{t("NotInformed")}</option>
                {REFLEX_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`ReflexStatus_${s}`)}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </Group>

      <Group title={t("FeedingEliminations")}>
        <div className="grid gap-3 sm:grid-cols-3">
          <SelectField label={t("Feeding")} value={value.feeding} onChange={(v) => set("feeding", v)} options={FEEDINGS} prefix="Feeding_" />
          {ELIMINATION_ITEMS.map((k) => (
            <label key={k} className="space-y-1.5 text-sm">
              <span className="font-medium">{t(`Elimination_${k}`)}</span>
              <select
                value={value.eliminations[k] ?? ""}
                onChange={(e) => set("eliminations", { ...value.eliminations, [k]: e.target.value })}
                className={inputCls}
              >
                <option value="">{t("NotInformed")}</option>
                {ELIMINATION_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`EliminationStatus_${s}`)}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </Group>

      <Group title={t("Intercurrences")}>
        <div className="grid gap-3 sm:grid-cols-2">
          <TriBoolField label={t("Hypoglycemia")} value={value.hypoglycemia} onChange={(v) => set("hypoglycemia", v)} />
          <TriBoolField label={t("Hypothermia")} value={value.hypothermia} onChange={(v) => set("hypothermia", v)} />
          <TriBoolField label={t("SkinToSkin")} value={value.skin_to_skin_1h} onChange={(v) => set("skin_to_skin_1h", v)} />
          <TriBoolField
            label={t("CongenitalMalformation")}
            value={value.congenital_malformation}
            onChange={(v) => set("congenital_malformation", v)}
          />
        </div>
        {value.congenital_malformation === true && (
          <TextField
            label={t("MalformationDescription")}
            value={value.congenital_malformation_desc}
            onChange={(v) => set("congenital_malformation_desc", v)}
          />
        )}
        <div>
          <span className="text-sm font-medium">{t("Immunization")}</span>
          <div className="mt-1.5 flex flex-wrap gap-x-6 gap-y-2">
            {IMMUNIZATION_ITEMS.map((k) => (
              <label key={k} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={value.immunization[k] === true}
                  onChange={(e) => set("immunization", { ...value.immunization, [k]: e.target.checked })}
                  className="size-4 rounded border-input"
                />
                {t(`Immunization_${k}`)}
              </label>
            ))}
          </div>
        </div>
        <div>
          <span className="text-sm font-medium">{t("Reanimation")}</span>
          <div className="mt-1.5 grid gap-1 sm:grid-cols-3">
            {REANIMATION_STEPS.map((o) => (
              <label key={o} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={value.reanimation.includes(o)}
                  onChange={() => toggleReanim(o)}
                  className="size-4 rounded border-input"
                />
                {t(`Reanim_${o}`)}
              </label>
            ))}
          </div>
        </div>
      </Group>

      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">{t("Notes")}</span>
        <textarea
          value={value.notes}
          onChange={(e) => set("notes", e.target.value)}
          rows={2}
          className={inputCls}
        />
      </label>
    </div>
  );
}
