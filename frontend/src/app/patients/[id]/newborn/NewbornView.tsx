"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Baby, Save, Trash2, Plus } from "lucide-react";
import { createNewbornRecord, updateNewbornRecord, deleteNewbornRecord } from "@/lib/api";
import { NewbornFields } from "./NewbornFields";
import { emptyNewbornForm, newbornFormFromRecord, newbornPayload, type NewbornForm } from "./newbornModel";

export type OutcomeOption = {
  pregnancyId: string;
  pregnancyLabel: string;
  outcomeType: string;
  outcomeDate: string;
  record: any | null;
};

export function NewbornView({
  patientId,
  outcomes,
}: {
  patientId: string;
  outcomes: OutcomeOption[];
}) {
  const t = useTranslations("Newborn");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState("");
  // Local mirror of each outcome's record so create/update/delete reflect at once.
  const [recMap, setRecMap] = useState<Record<string, any | null>>(
    Object.fromEntries(outcomes.map((o) => [o.pregnancyId, o.record])),
  );
  const [selected, setSelected] = useState<string>(outcomes[0]?.pregnancyId ?? "");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NewbornForm>(emptyNewbornForm());

  const current = outcomes.find((o) => o.pregnancyId === selected);
  const currentRecord = selected ? recMap[selected] ?? null : null;

  function pick(id: string) {
    setSelected(id);
    const rec = recMap[id] ?? null;
    setForm(rec ? newbornFormFromRecord(rec) : emptyNewbornForm());
    setShowForm(false);
    setError("");
  }

  function openCreate() {
    setForm(emptyNewbornForm());
    setShowForm(true);
    setError("");
  }

  function openEdit() {
    setForm(currentRecord ? newbornFormFromRecord(currentRecord) : emptyNewbornForm());
    setShowForm(true);
    setError("");
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError("");
    start(async () => {
      try {
        const payload = newbornPayload(form);
        const rec = currentRecord
          ? await updateNewbornRecord(currentRecord.id, payload)
          : await createNewbornRecord(patientId, selected, payload);
        setRecMap((m) => ({ ...m, [selected]: rec }));
        setShowForm(false);
        router.refresh();
      } catch {
        setError(t("ErrorGeneric"));
      }
    });
  }

  function remove() {
    if (!currentRecord) return;
    setError("");
    start(async () => {
      try {
        await deleteNewbornRecord(currentRecord.id);
        setRecMap((m) => ({ ...m, [selected]: null }));
        setShowForm(false);
        router.refresh();
      } catch {
        setError(t("ErrorGeneric"));
      }
    });
  }

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">{t("Note")}</p>

      {outcomes.length === 0 ? (
        <div className="rounded-2xl border bg-card py-12 text-center text-muted-foreground">{t("NoOutcomes")}</div>
      ) : (
        <section className="rounded-xl border bg-card p-5">
          {/* Vínculo ao desfecho/gestação — the 1:1 anchor is chosen here. */}
          <label className="block max-w-md space-y-1.5 text-sm">
            <span className="font-medium">{t("Outcome")}</span>
            <select
              className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
              value={selected}
              onChange={(e) => pick(e.target.value)}
            >
              {outcomes.map((o) => (
                <option key={o.pregnancyId} value={o.pregnancyId}>
                  {o.pregnancyLabel} · {t(`OutcomeType_${o.outcomeType}`)} · {o.outcomeDate}
                  {recMap[o.pregnancyId] ? ` · ${t("HasRecord")}` : ""}
                </option>
              ))}
            </select>
          </label>

          {error && (
            <div className="mt-3 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>
          )}

          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="flex size-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Baby className="size-5" />
              </span>
              <span className="text-sm font-medium">
                {current ? `${current.pregnancyLabel} · ${t(`OutcomeType_${current.outcomeType}`)}` : ""}
              </span>
              {currentRecord && (
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                  {t("HasRecord")}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!currentRecord ? (
                <button
                  type="button"
                  onClick={openCreate}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  <Plus className="size-4" />
                  {t("Add")}
                </button>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={openEdit}
                    className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted transition-colors"
                  >
                    {t("Edit")}
                  </button>
                  <button
                    type="button"
                    disabled={pending}
                    onClick={remove}
                    className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="size-4" />
                    {t("Delete")}
                  </button>
                </>
              )}
            </div>
          </div>

          {currentRecord && !showForm && <NewbornSummary record={currentRecord} />}

          {showForm && (
            <form onSubmit={submit} className="mt-4 space-y-3">
              <NewbornFields value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} />
              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={pending}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  <Save className="size-4" />
                  {t("Save")}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
                >
                  {t("Cancel")}
                </button>
              </div>
            </form>
          )}
        </section>
      )}
    </div>
  );
}

// Read-only projection of a saved record — only the fields that were set.
function NewbornSummary({ record }: { record: any }) {
  const t = useTranslations("Newborn");
  const parts: string[] = [];
  const tri = (v: unknown) => (v === true ? t("Bool_yes") : v === false ? t("Bool_no") : null);

  if (record.sex) parts.push(`${t("Sex")}: ${t(`Sex_${record.sex}`)}`);
  if (record.delivery_type) parts.push(`${t("DeliveryType")}: ${t(`Delivery_${record.delivery_type}`)}`);
  if (record.gestational_age_weeks != null) parts.push(`${t("GestationalAgeWeeks")}: ${record.gestational_age_weeks}`);
  if (record.classification) parts.push(`${t("Classification")}: ${t(`Class_${record.classification}`)}`);
  if (record.apgar_1 != null) parts.push(`${t("Apgar1")}: ${record.apgar_1}`);
  if (record.apgar_5 != null) parts.push(`${t("Apgar5")}: ${record.apgar_5}`);
  if (record.apgar_10 != null) parts.push(`${t("Apgar10")}: ${record.apgar_10}`);
  if (record.weight_g != null) parts.push(`${t("WeightG")}: ${record.weight_g}`);
  if (record.length_cm != null) parts.push(`${t("LengthCm")}: ${record.length_cm}`);
  if (record.pc_cm != null) parts.push(`${t("PcCm")}: ${record.pc_cm}`);
  if (record.pt_cm != null) parts.push(`${t("PtCm")}: ${record.pt_cm}`);
  if (record.pa_cm != null) parts.push(`${t("PaCm")}: ${record.pa_cm}`);
  if (record.feeding) parts.push(`${t("Feeding")}: ${t(`Feeding_${record.feeding}`)}`);
  if (record.cord_clamping) parts.push(`${t("CordClamping")}: ${t(`Cord_${record.cord_clamping}`)}`);
  const hypo = tri(record.hypoglycemia);
  if (hypo) parts.push(`${t("Hypoglycemia")}: ${hypo}`);
  const hypother = tri(record.hypothermia);
  if (hypother) parts.push(`${t("Hypothermia")}: ${hypother}`);
  const s2s = tri(record.skin_to_skin_1h);
  if (s2s) parts.push(`${t("SkinToSkin")}: ${s2s}`);
  if (record.congenital_malformation != null && record.congenital_malformation !== false) {
    const v = typeof record.congenital_malformation === "string" ? record.congenital_malformation : t("Bool_yes");
    parts.push(`${t("CongenitalMalformation")}: ${v}`);
  }
  if (record.notes) parts.push(record.notes);

  if (parts.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-0.5 border-t pt-3 text-xs text-muted-foreground">
      {parts.map((p, i) => (
        <span key={i}>{p}</span>
      ))}
    </div>
  );
}
