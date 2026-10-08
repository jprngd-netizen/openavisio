"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Save, Loader2, Check } from "lucide-react";
import {
  saveClinicalHistory,
  createCondition,
  updateCondition,
  deleteCondition,
  createMedication,
  updateMedication,
  deleteMedication,
} from "@/lib/api";
import { CidCombobox } from "@/components/CidCombobox";

type Employment = { company: string; role: string; start: string; end: string };
type Exposure = { category: string; agent: string; duration: string; ppe: boolean };

type Props = {
  patientId: string;
  history: any | null;
  conditions: any[];
  medications: any[];
};

const CATEGORIES = ["physical", "chemical", "biological", "ergonomic", "psychosocial"] as const;
const EMPTY_EMP: Employment = { company: "", role: "", start: "", end: "" };
const EMPTY_EXP: Exposure = { category: "", agent: "", duration: "", ppe: false };

const inputCls =
  "w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

export function ClinicalHistoryView({ patientId, history, conditions, medications }: Props) {
  const t = useTranslations("OccupationalClinicalHistory");
  const router = useRouter();

  const [personal, setPersonal] = useState(history?.personal_history ?? "");
  const [family, setFamily] = useState(history?.family_history ?? "");
  const [surgical, setSurgical] = useState(history?.surgical_history ?? "");
  const [allergies, setAllergies] = useState(history?.allergies ?? "");
  const [habits, setHabits] = useState(history?.habits ?? "");
  const [employments, setEmployments] = useState<Employment[]>(
    (history?.previous_employments ?? []).map((e: any) => ({
      company: e.company ?? "", role: e.role ?? "", start: e.start ?? "", end: e.end ?? "",
    })),
  );
  const [exposures, setExposures] = useState<Exposure[]>(
    (history?.exposures ?? []).map((e: any) => ({
      category: e.category ?? "", agent: e.agent ?? "", duration: e.duration ?? "", ppe: !!e.ppe,
    })),
  );

  const [saving, startSave] = useTransition();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function save() {
    setError(null);
    setSaved(false);
    startSave(async () => {
      try {
        await saveClinicalHistory(patientId, {
          personal_history: personal || null,
          family_history: family || null,
          surgical_history: surgical || null,
          allergies: allergies || null,
          habits: habits || null,
          previous_employments: employments.filter((e) => e.company || e.role || e.start || e.end),
          exposures: exposures.filter((e) => e.category || e.agent || e.duration),
        });
        setSaved(true);
        router.refresh();
      } catch (e: any) {
        setError(e?.message ?? "error");
      }
    });
  }

  return (
    <div className="space-y-6">
      {/* (A) Clinical history — free text, editable. */}
      <Card title={t("ClinicalTitle")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("PersonalHistory")} value={personal} onChange={setPersonal} />
          <Field label={t("FamilyHistory")} value={family} onChange={setFamily} />
          <Field label={t("SurgicalHistory")} value={surgical} onChange={setSurgical} />
          <Field label={t("Allergies")} value={allergies} onChange={setAllergies} />
          <div className="md:col-span-2">
            <Field label={t("Habits")} value={habits} onChange={setHabits} />
          </div>
        </div>
      </Card>

      {/* (B) Occupational history — editable lists. */}
      <Card title={t("OccupationalTitle")}>
        <div className="space-y-6">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">{t("PreviousEmployments")}</span>
              <button
                type="button"
                onClick={() => setEmployments((l) => [...l, { ...EMPTY_EMP }])}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                <Plus className="size-3.5" /> {t("Add")}
              </button>
            </div>
            {employments.length === 0 && <p className="text-xs text-muted-foreground">{t("None")}</p>}
            <div className="space-y-2">
              {employments.map((e, i) => (
                <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto_auto_auto]">
                  <input className={inputCls} placeholder={t("Company")} value={e.company}
                    onChange={(ev) => setEmployments((l) => l.map((x, j) => (j === i ? { ...x, company: ev.target.value } : x)))} />
                  <input className={inputCls} placeholder={t("Role")} value={e.role}
                    onChange={(ev) => setEmployments((l) => l.map((x, j) => (j === i ? { ...x, role: ev.target.value } : x)))} />
                  <input type="date" className={inputCls} value={e.start}
                    onChange={(ev) => setEmployments((l) => l.map((x, j) => (j === i ? { ...x, start: ev.target.value } : x)))} />
                  <input type="date" className={inputCls} value={e.end}
                    onChange={(ev) => setEmployments((l) => l.map((x, j) => (j === i ? { ...x, end: ev.target.value } : x)))} />
                  <button type="button" onClick={() => setEmployments((l) => l.filter((_, j) => j !== i))}
                    className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">{t("Exposures")}</span>
              <button type="button" onClick={() => setExposures((l) => [...l, { ...EMPTY_EXP }])}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                <Plus className="size-3.5" /> {t("Add")}
              </button>
            </div>
            {exposures.length === 0 && <p className="text-xs text-muted-foreground">{t("None")}</p>}
            <div className="space-y-2">
              {exposures.map((e, i) => (
                <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[auto_1fr_auto_auto_auto]">
                  <select className={inputCls} value={e.category}
                    onChange={(ev) => setExposures((l) => l.map((x, j) => (j === i ? { ...x, category: ev.target.value } : x)))}>
                    <option value="">{t("Category")}</option>
                    {CATEGORIES.map((c) => <option key={c} value={c}>{t(`Category_${c}`)}</option>)}
                  </select>
                  <input className={inputCls} placeholder={t("Agent")} value={e.agent}
                    onChange={(ev) => setExposures((l) => l.map((x, j) => (j === i ? { ...x, agent: ev.target.value } : x)))} />
                  <input className={inputCls} placeholder={t("Duration")} value={e.duration}
                    onChange={(ev) => setExposures((l) => l.map((x, j) => (j === i ? { ...x, duration: ev.target.value } : x)))} />
                  <label className="inline-flex items-center gap-1.5 whitespace-nowrap px-1 text-xs">
                    <input type="checkbox" checked={e.ppe}
                      onChange={(ev) => setExposures((l) => l.map((x, j) => (j === i ? { ...x, ppe: ev.target.checked } : x)))} />
                    {t("Ppe")}
                  </label>
                  <button type="button" onClick={() => setExposures((l) => l.filter((_, j) => j !== i))}
                    className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                    <Trash2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <button type="button" onClick={save} disabled={saving}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60">
          {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
          {t("Save")}
        </button>
        {saved && !saving && <span className="inline-flex items-center gap-1 text-sm text-emerald-600"><Check className="size-4" /> {t("Saved")}</span>}
        {error && <span className="text-sm text-destructive">{error}</span>}
      </div>

      {/* (C) Derived antecedents — the canonical resources, edited in place. */}
      <ConditionsEditor patientId={patientId} items={conditions} />
      <MedicationsEditor patientId={patientId} items={medications} />
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">{label}</span>
      <textarea className={`${inputCls} min-h-20`} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function ConditionsEditor({ patientId, items }: { patientId: string; items: any[] }) {
  const t = useTranslations("OccupationalClinicalHistory");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState({ code: "", code_display: "", onset_date_time: "", severity: "" });

  function add() {
    if (!draft.code_display.trim()) return;
    start(async () => {
      await createCondition(patientId, {
        code: draft.code || null,
        code_display: draft.code_display.trim(),
        onset_date_time: draft.onset_date_time || null,
        severity: draft.severity || null,
        clinical_status: "active",
      });
      setDraft({ code: "", code_display: "", onset_date_time: "", severity: "" });
      router.refresh();
    });
  }

  return (
    <Card title={t("DerivedDiagnoses")}>
      <p className="mb-3 text-xs text-muted-foreground">{t("DerivedNote")}</p>
      <div className="space-y-2">
        {items.map((c) => (
          <ConditionRow key={c.id} condition={c} busy={pending} onChange={() => start(async () => { router.refresh(); })} />
        ))}
        {items.length === 0 && <p className="text-xs text-muted-foreground">{t("None")}</p>}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[2fr_auto_auto_auto]">
        <CidCombobox
          className={inputCls}
          placeholder={t("Diagnosis")}
          value={draft.code_display}
          onSelect={(opt, text) => setDraft((d) => ({ ...d, code_display: text, code: opt?.code ?? "" }))}
        />
        <input type="date" className={inputCls} value={draft.onset_date_time}
          onChange={(e) => setDraft({ ...draft, onset_date_time: e.target.value })} />
        <select className={inputCls} value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })}>
          <option value="">{t("Severity")}</option>
          {["mild", "moderate", "severe"].map((s) => <option key={s} value={s}>{t(`Severity_${s}`)}</option>)}
        </select>
        <button type="button" onClick={add} disabled={pending}
          className="inline-flex items-center justify-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-60">
          <Plus className="size-4" /> {t("Add")}
        </button>
      </div>
    </Card>
  );
}

function ConditionRow({ condition, busy, onChange }: { condition: any; busy: boolean; onChange: () => void }) {
  const t = useTranslations("OccupationalClinicalHistory");
  const [row, setRow] = useState({
    code: condition.code ?? "",
    code_display: condition.code_display ?? "",
    onset_date_time: condition.onset_date_time ?? "",
    severity: condition.severity ?? "",
    clinical_status: condition.clinical_status ?? "active",
  });
  const [pending, start] = useTransition();

  return (
    <div className="grid grid-cols-1 gap-2 rounded-md border p-2 sm:grid-cols-[2fr_auto_auto_auto_auto]">
      <CidCombobox
        className={inputCls}
        value={row.code_display}
        onSelect={(opt, text) => setRow((r) => ({ ...r, code_display: text, code: opt?.code ?? "" }))}
      />
      <input type="date" className={inputCls} value={row.onset_date_time} onChange={(e) => setRow({ ...row, onset_date_time: e.target.value })} />
      <select className={inputCls} value={row.severity} onChange={(e) => setRow({ ...row, severity: e.target.value })}>
        <option value="">{t("Severity")}</option>
        {["mild", "moderate", "severe"].map((s) => <option key={s} value={s}>{t(`Severity_${s}`)}</option>)}
      </select>
      <select className={inputCls} value={row.clinical_status} onChange={(e) => setRow({ ...row, clinical_status: e.target.value })}>
        {["active", "resolved", "inactive"].map((s) => <option key={s} value={s}>{t(`Status_${s}`)}</option>)}
      </select>
      <div className="flex items-center gap-1">
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await updateCondition(condition.id, { ...row, code: row.code || null, onset_date_time: row.onset_date_time || null, severity: row.severity || null }); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50">
          <Save className="size-4" />
        </button>
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await deleteCondition(condition.id); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50">
          <Trash2 className="size-4" />
        </button>
      </div>
    </div>
  );
}

function MedicationsEditor({ patientId, items }: { patientId: string; items: any[] }) {
  const t = useTranslations("OccupationalClinicalHistory");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState({ medication_display: "", dosage_text: "" });

  function add() {
    if (!draft.medication_display.trim()) return;
    start(async () => {
      await createMedication(patientId, {
        medication_display: draft.medication_display.trim(),
        dosage_text: draft.dosage_text || null,
        status: "active",
      });
      setDraft({ medication_display: "", dosage_text: "" });
      router.refresh();
    });
  }

  return (
    <Card title={t("DerivedMedications")}>
      <p className="mb-3 text-xs text-muted-foreground">{t("DerivedNote")}</p>
      <div className="space-y-2">
        {items.map((m) => (
          <MedicationRow key={m.id} medication={m} busy={pending} onChange={() => start(async () => { router.refresh(); })} />
        ))}
        {items.length === 0 && <p className="text-xs text-muted-foreground">{t("None")}</p>}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[2fr_2fr_auto]">
        <input className={inputCls} placeholder={t("Medication")} value={draft.medication_display}
          onChange={(e) => setDraft({ ...draft, medication_display: e.target.value })} />
        <input className={inputCls} placeholder={t("Dosage")} value={draft.dosage_text}
          onChange={(e) => setDraft({ ...draft, dosage_text: e.target.value })} />
        <button type="button" onClick={add} disabled={pending}
          className="inline-flex items-center justify-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-60">
          <Plus className="size-4" /> {t("Add")}
        </button>
      </div>
    </Card>
  );
}

function MedicationRow({ medication, busy, onChange }: { medication: any; busy: boolean; onChange: () => void }) {
  const t = useTranslations("OccupationalClinicalHistory");
  const [row, setRow] = useState({
    medication_display: medication.medication_display ?? "",
    dosage_text: medication.dosage_text ?? "",
    status: medication.status ?? "active",
  });
  const [pending, start] = useTransition();

  return (
    <div className="grid grid-cols-1 gap-2 rounded-md border p-2 sm:grid-cols-[2fr_2fr_auto_auto]">
      <input className={inputCls} value={row.medication_display} onChange={(e) => setRow({ ...row, medication_display: e.target.value })} />
      <input className={inputCls} value={row.dosage_text} onChange={(e) => setRow({ ...row, dosage_text: e.target.value })} />
      <select className={inputCls} value={row.status} onChange={(e) => setRow({ ...row, status: e.target.value })}>
        {["active", "stopped", "completed"].map((s) => <option key={s} value={s}>{t(`MedStatus_${s}`)}</option>)}
      </select>
      <div className="flex items-center gap-1">
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await updateMedication(medication.id, { ...row, dosage_text: row.dosage_text || null }); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50">
          <Save className="size-4" />
        </button>
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await deleteMedication(medication.id); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50">
          <Trash2 className="size-4" />
        </button>
      </div>
    </div>
  );
}
