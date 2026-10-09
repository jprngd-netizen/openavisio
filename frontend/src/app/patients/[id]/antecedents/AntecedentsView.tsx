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
  createAllergy,
  updateAllergy,
  deleteAllergy,
} from "@/lib/api";
import { CidCombobox } from "@/components/CidCombobox";

type Props = {
  patientId: string;
  history: any | null;
  conditions: any[];
  medications: any[];
  allergies: any[];
};

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

export function AntecedentsView({ patientId, history, conditions, medications, allergies }: Props) {
  const t = useTranslations("Antecedents");
  const router = useRouter();

  const [personal, setPersonal] = useState(history?.personal_history ?? "");
  const [family, setFamily] = useState(history?.family_history ?? "");
  const [surgical, setSurgical] = useState(history?.surgical_history ?? "");
  // Legacy free-text allergies: the structured `allergies` resource replaces it in
  // the UI, but the column is kept and preserved on save (never wiped).
  const [legacyAllergies] = useState(history?.allergies ?? "");
  const [habits, setHabits] = useState(history?.habits ?? "");

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
          allergies: legacyAllergies || null,
          habits: habits || null,
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
      {/* (A) Antecedentes clínicos — free text, editable. */}
      <Card title={t("ClinicalTitle")}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={t("PersonalHistory")} value={personal} onChange={setPersonal} />
          <Field label={t("FamilyHistory")} value={family} onChange={setFamily} />
          <Field label={t("SurgicalHistory")} value={surgical} onChange={setSurgical} />
          <div className="md:col-span-2">
            <Field label={t("Habits")} value={habits} onChange={setHabits} />
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

      {/* (B) Derived antecedents — the canonical resources, edited in place. */}
      <AllergiesEditor patientId={patientId} items={allergies} />
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
  const t = useTranslations("Antecedents");
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
  const t = useTranslations("Antecedents");
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
  const t = useTranslations("Antecedents");
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
  const t = useTranslations("Antecedents");
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

const SEVERITIES = ["mild", "moderate", "severe", "life_threatening"];
const CRITICALITIES = ["low", "high", "unable_to_assess"];
const ALLERGY_STATUSES = ["active", "inactive", "resolved"];

function AllergiesEditor({ patientId, items }: { patientId: string; items: any[] }) {
  const t = useTranslations("Antecedents");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState({
    substance_display: "",
    reaction: "",
    severity: "",
    criticality: "unable_to_assess",
    clinical_status: "active",
    onset: "",
  });

  function add() {
    if (!draft.substance_display.trim()) return;
    start(async () => {
      await createAllergy(patientId, {
        substance_display: draft.substance_display.trim(),
        reaction: draft.reaction || null,
        severity: draft.severity || null,
        criticality: draft.criticality,
        clinical_status: draft.clinical_status,
        onset: draft.onset || null,
      });
      setDraft({ substance_display: "", reaction: "", severity: "", criticality: "unable_to_assess", clinical_status: "active", onset: "" });
      router.refresh();
    });
  }

  return (
    <Card title={t("Allergies")}>
      <p className="mb-3 text-xs text-muted-foreground">{t("AllergiesNote")}</p>
      <div className="space-y-2">
        {items.map((a) => (
          <AllergyRow key={a.id} allergy={a} busy={pending} onChange={() => start(async () => { router.refresh(); })} />
        ))}
        {items.length === 0 && <p className="text-xs text-muted-foreground">{t("None")}</p>}
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-[2fr_2fr_auto_auto_auto_auto_auto]">
        <input className={inputCls} placeholder={t("Substance")} value={draft.substance_display}
          onChange={(e) => setDraft({ ...draft, substance_display: e.target.value })} data-testid="allergy-draft-substance" />
        <input className={inputCls} placeholder={t("Reaction")} value={draft.reaction}
          onChange={(e) => setDraft({ ...draft, reaction: e.target.value })} />
        <select className={inputCls} value={draft.severity} onChange={(e) => setDraft({ ...draft, severity: e.target.value })} aria-label={t("Severity")}>
          <option value="">{t("Severity")}</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{t(`Severity_${s}`)}</option>)}
        </select>
        <select className={inputCls} value={draft.criticality} onChange={(e) => setDraft({ ...draft, criticality: e.target.value })} aria-label={t("Criticality")}>
          {CRITICALITIES.map((c) => <option key={c} value={c}>{t(`Criticality_${c}`)}</option>)}
        </select>
        <select className={inputCls} value={draft.clinical_status} onChange={(e) => setDraft({ ...draft, clinical_status: e.target.value })} aria-label={t("ClinicalStatus")}>
          {ALLERGY_STATUSES.map((s) => <option key={s} value={s}>{t(`Status_${s}`)}</option>)}
        </select>
        <input type="date" className={inputCls} value={draft.onset} onChange={(e) => setDraft({ ...draft, onset: e.target.value })} aria-label={t("Onset")} />
        <button type="button" onClick={add} disabled={pending}
          className="inline-flex items-center justify-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-60">
          <Plus className="size-4" /> {t("Add")}
        </button>
      </div>
    </Card>
  );
}

function AllergyRow({ allergy, busy, onChange }: { allergy: any; busy: boolean; onChange: () => void }) {
  const t = useTranslations("Antecedents");
  const [row, setRow] = useState({
    substance_display: allergy.substance_display ?? "",
    reaction: allergy.reaction ?? "",
    severity: allergy.severity ?? "",
    criticality: allergy.criticality ?? "unable_to_assess",
    clinical_status: allergy.clinical_status ?? "active",
    onset: allergy.onset ? String(allergy.onset).slice(0, 10) : "",
  });
  const [pending, start] = useTransition();

  return (
    <div className="grid grid-cols-1 gap-2 rounded-md border p-2 sm:grid-cols-2 lg:grid-cols-[2fr_2fr_auto_auto_auto_auto_auto]">
      <input className={inputCls} value={row.substance_display} onChange={(e) => setRow({ ...row, substance_display: e.target.value })} />
      <input className={inputCls} value={row.reaction} onChange={(e) => setRow({ ...row, reaction: e.target.value })} />
      <select className={inputCls} value={row.severity} onChange={(e) => setRow({ ...row, severity: e.target.value })} aria-label={t("Severity")}>
        <option value="">{t("Severity")}</option>
        {SEVERITIES.map((s) => <option key={s} value={s}>{t(`Severity_${s}`)}</option>)}
      </select>
      <select className={inputCls} value={row.criticality} onChange={(e) => setRow({ ...row, criticality: e.target.value })} aria-label={t("Criticality")}>
        {CRITICALITIES.map((c) => <option key={c} value={c}>{t(`Criticality_${c}`)}</option>)}
      </select>
      <select className={inputCls} value={row.clinical_status} onChange={(e) => setRow({ ...row, clinical_status: e.target.value })} aria-label={t("ClinicalStatus")}>
        {ALLERGY_STATUSES.map((s) => <option key={s} value={s}>{t(`Status_${s}`)}</option>)}
      </select>
      <input type="date" className={inputCls} value={row.onset} onChange={(e) => setRow({ ...row, onset: e.target.value })} aria-label={t("Onset")} />
      <div className="flex items-center gap-1">
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await updateAllergy(allergy.id, { ...row, reaction: row.reaction || null, severity: row.severity || null, onset: row.onset || null }); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50">
          <Save className="size-4" />
        </button>
        <button type="button" disabled={busy || pending}
          onClick={() => start(async () => { await deleteAllergy(allergy.id); onChange(); })}
          className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50">
          <Trash2 className="size-4" />
        </button>
      </div>
    </div>
  );
}
