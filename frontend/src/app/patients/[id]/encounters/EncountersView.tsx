"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { createEncounter, updateEncounter, deleteEncounter } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { MEASUREMENT_TYPES, measurementType, computeBmi } from "@/lib/measurementTypes";
import { CidCombobox } from "@/components/CidCombobox";
import { Plus, X, Pencil, Trash2, Activity } from "lucide-react";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const labelCls = "text-sm font-medium";

const TYPE_KEYS = ["Consulta", "Retorno", "Teleconsulta", "Urgencia", "Evolucao", "Procedimento"] as const;

const EMPTY = {
  encounter_type: "",
  encounter_date: "",
  chief_complaint: "",
  history: "",
  physical_exam: "",
  assessment: "",
  plan: "",
  cid10_code: "",
  cid10_display: "",
  notes: "",
};

type FormState = typeof EMPTY;

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  // datetime-local wants "YYYY-MM-DDTHH:MM"; an ISO-8601 string may carry seconds/zone.
  return String(iso).slice(0, 16);
}

export function EncountersView({ patientId, encounters }: { patientId: string; encounters: any[] }) {
  const t = useTranslations("Enc");
  const tm = useTranslations("Measurement");
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [vitals, setVitals] = useState<Record<string, string>>({});

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  // Vital signs live in the consultation: they are written as linked Observation
  // rows (see the backend), so they also feed the measurements history/graphs.
  function setVital(code: string, value: string) {
    setVitals((v) => {
      const next = { ...v, [code]: value };
      // BMI is always derived from weight and height, so recompute on every change
      // rather than only while blank: entering the height digit by digit ("1" → "189")
      // otherwise freezes the absurd value computed from the first keystroke.
      if (code === "body-weight" || code === "body-height") {
        const bmi = computeBmi(parseFloat(next["body-weight"]), parseFloat(next["body-height"]));
        if (bmi != null) next["bmi"] = String(bmi);
        else delete next["bmi"];
      }
      return next;
    });
  }

  function reset() {
    setForm(EMPTY);
    setVitals({});
    setEditingId(null);
    setError("");
  }

  function close() {
    reset();
    setOpen(false);
  }

  function openCreate() {
    reset();
    setOpen(true);
  }

  function openEdit(e: any) {
    setEditingId(e.id);
    setForm({
      encounter_type: e.encounter_type ?? "",
      encounter_date: toLocalInput(e.encounter_date),
      chief_complaint: e.chief_complaint ?? "",
      history: e.history ?? "",
      physical_exam: e.physical_exam ?? "",
      assessment: e.assessment ?? "",
      plan: e.plan ?? "",
      cid10_code: e.cid10_code ?? "",
      cid10_display: e.cid10_display ?? "",
      notes: e.notes ?? "",
    });
    setVitals(
      Object.fromEntries(
        (e.measurements ?? [])
          .filter((m: any) => m.value_quantity != null)
          .map((m: any) => [m.code, String(m.value_quantity)])
      )
    );
    setError("");
    setOpen(true);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const measurements = MEASUREMENT_TYPES.filter((m) => (vitals[m.code] ?? "").trim() !== "")
      .map((m) => ({
        code: m.code,
        code_display: tm(m.key),
        value_quantity: parseFloat(vitals[m.code]),
        value_unit: m.unit,
      }))
      .filter((m) => !Number.isNaN(m.value_quantity));
    const payload = {
      encounter_type: form.encounter_type || null,
      encounter_date: form.encounter_date || null,
      chief_complaint: form.chief_complaint || null,
      history: form.history || null,
      physical_exam: form.physical_exam || null,
      assessment: form.assessment || null,
      plan: form.plan || null,
      cid10_code: form.cid10_code || null,
      cid10_display: form.cid10_display || null,
      notes: form.notes || null,
      measurements,
    };
    startTransition(async () => {
      try {
        if (editingId) {
          await updateEncounter(editingId, payload);
        } else {
          await createEncounter(patientId, payload);
        }
        close();
        router.refresh();
      } catch {
        setError(t("LoadError"));
      }
    });
  }

  function handleDelete(id: string) {
    if (confirmId !== id) { setConfirmId(id); return; }
    startTransition(async () => {
      await deleteEncounter(id);
      setConfirmId(null);
      router.refresh();
    });
  }

  function typeLabel(raw: string | null | undefined): string {
    if (!raw) return "";
    if ((TYPE_KEYS as readonly string[]).includes(raw)) return t(`Types.${raw}`);
    return raw;
  }

  function vitalLabel(code: string, fallback: string | null): string {
    const mt = measurementType(code);
    return mt ? tm(mt.key) : (fallback ?? code);
  }

  const blocks: { key: keyof FormState; label: string }[] = [
    { key: "chief_complaint", label: t("ChiefComplaint") },
    { key: "history", label: t("History") },
    { key: "physical_exam", label: t("PhysicalExam") },
    { key: "assessment", label: t("Assessment") },
    { key: "plan", label: t("Plan") },
    { key: "notes", label: t("Notes") },
  ];

  return (
    <div>
      <div className="mb-6 flex items-center justify-end">
        <button
          onClick={() => (open ? close() : openCreate())}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          {t("AddTitle")}
        </button>
      </div>

      {open && (
        <div className="rounded-xl border bg-card p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold">{editingId ? t("EditTitle") : t("AddTitle")}</span>
            <button onClick={close} className="text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm mb-4">{error}</div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className={labelCls}>{t("TypeLabel")}</label>
                <select
                  value={form.encounter_type}
                  onChange={(e) => set("encounter_type", e.target.value)}
                  className={inputCls}
                >
                  <option value="">—</option>
                  {TYPE_KEYS.map((k) => (
                    <option key={k} value={k}>{t(`Types.${k}`)}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <label className={labelCls}>{t("DateLabel")}</label>
                <input
                  type="datetime-local"
                  value={form.encounter_date}
                  onChange={(e) => set("encounter_date", e.target.value)}
                  className={inputCls}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className={labelCls}>{t("ChiefComplaint")}</label>
              <textarea
                rows={2}
                value={form.chief_complaint}
                onChange={(e) => set("chief_complaint", e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>{t("History")}</label>
              <textarea
                rows={3}
                value={form.history}
                onChange={(e) => set("history", e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>{t("PhysicalExam")}</label>
              <textarea
                rows={3}
                value={form.physical_exam}
                onChange={(e) => set("physical_exam", e.target.value)}
                className={inputCls}
              />
            </div>

            <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
              <div className="flex items-center gap-1.5">
                <Activity className="h-4 w-4 text-muted-foreground" />
                <span className={labelCls}>{t("Vitals")}</span>
              </div>
              <p className="text-xs text-muted-foreground">{t("VitalsHint")}</p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {MEASUREMENT_TYPES.map((m) => (
                  <div key={m.code} className="space-y-1">
                    <label className="text-xs text-muted-foreground">{tm(m.key)}</label>
                    <div className="relative">
                      <input
                        type="number"
                        step="any"
                        inputMode="decimal"
                        value={vitals[m.code] ?? ""}
                        onChange={(e) => setVital(m.code, e.target.value)}
                        className={`${inputCls} pr-12`}
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                        {m.unit}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className={labelCls}>{t("Assessment")}</label>
              <textarea
                rows={3}
                value={form.assessment}
                onChange={(e) => set("assessment", e.target.value)}
                className={inputCls}
              />
            </div>
            <div className="space-y-1.5">
              <label className={labelCls}>{t("Plan")}</label>
              <textarea
                rows={3}
                value={form.plan}
                onChange={(e) => set("plan", e.target.value)}
                className={inputCls}
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className={labelCls}>{t("Cid10Code")}</label>
                <input
                  type="text"
                  value={form.cid10_code}
                  onChange={(e) => set("cid10_code", e.target.value)}
                  className={inputCls}
                />
              </div>
              <div className="space-y-1.5">
                <label className={labelCls}>{t("Cid10Display")}</label>
                <CidCombobox
                  className={inputCls}
                  value={form.cid10_display}
                  onSelect={(opt, text) => {
                    if (opt) {
                      set("cid10_code", opt.code);
                      set("cid10_display", opt.description);
                    } else {
                      set("cid10_display", text);
                    }
                  }}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className={labelCls}>{t("Notes")}</label>
              <textarea
                rows={2}
                value={form.notes}
                onChange={(e) => set("notes", e.target.value)}
                className={inputCls}
              />
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {pending ? t("Saving") : t("Save")}
              </button>
              <button
                type="button"
                onClick={close}
                className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
              >
                {t("Cancel")}
              </button>
            </div>
          </form>
        </div>
      )}

      {encounters.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <div className="space-y-3">
          {encounters.map((e: any) => {
            const nonEmpty = blocks.filter((b) => e[b.key]);
            const vitalsRows = (e.measurements ?? []).filter((m: any) => m.value_quantity != null);
            return (
              <div key={e.id} className="rounded-xl border bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold">{formatDate(e.encounter_date)}</span>
                      {e.encounter_type && (
                        <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-xs font-medium text-cyan-700 dark:text-cyan-400">
                          {typeLabel(e.encounter_type)}
                        </span>
                      )}
                      {(e.cid10_code || e.cid10_display) && (
                        <span className="text-xs text-muted-foreground">
                          {e.cid10_code ? `${e.cid10_code}` : ""}
                          {e.cid10_code && e.cid10_display ? " · " : ""}
                          {e.cid10_display ?? ""}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => openEdit(e)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/70 transition-colors"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      {t("Edit")}
                    </button>
                    <button
                      onClick={() => handleDelete(e.id)}
                      onMouseLeave={() => setConfirmId((c) => (c === e.id ? null : c))}
                      disabled={pending}
                      title={confirmId === e.id ? t("ConfirmAgain") : t("Delete")}
                      className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
                        confirmId === e.id
                          ? "border-destructive bg-destructive text-destructive-foreground hover:bg-destructive/90"
                          : "border-border bg-muted text-foreground hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
                      }`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      {confirmId === e.id ? t("Confirm") : t("Delete")}
                    </button>
                  </div>
                </div>

                {vitalsRows.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2 border-t pt-3">
                    {vitalsRows.map((m: any) => (
                      <span
                        key={m.id ?? m.code}
                        className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs"
                      >
                        <span className="text-muted-foreground">{vitalLabel(m.code, m.code_display)}</span>
                        <span className="font-medium">
                          {m.value_quantity}
                          {m.value_unit ? ` ${m.value_unit}` : ""}
                        </span>
                      </span>
                    ))}
                  </div>
                )}

                {nonEmpty.length > 0 && (
                  <div className="mt-3 space-y-2 border-t pt-3">
                    {nonEmpty.map((b) => (
                      <div key={b.key}>
                        <div className="text-xs font-bold text-foreground">{b.label}</div>
                        <div className="whitespace-pre-wrap text-sm text-muted-foreground">{e[b.key]}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}