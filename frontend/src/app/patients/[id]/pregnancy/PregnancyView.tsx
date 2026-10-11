"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { formatDate } from "@/lib/utils";
import {
  getPregnancies,
  getObstetricSummary,
  createPregnancy,
  updatePregnancy,
  deletePregnancy,
} from "@/lib/api";
import { Baby, Plus, X, Trash2, Pencil, CalendarClock } from "lucide-react";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

const STATUSES = ["active", "completed", "miscarriage", "terminated", "ectopic", "fetal_death"] as const;

const STATUS_COLORS: Record<string, string> = {
  active: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
  completed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  miscarriage: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  terminated: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  ectopic: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
  fetal_death: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

type Episode = {
  id: string;
  status: string;
  lmp_date: string | null;
  estimated_due_date: string | null;
  ultrasound_due_date: string | null;
  ultrasound_date: string | null;
  ended_at: string | null;
  notes: string | null;
  gestational_age?: { weeks: number; days: number; basis: string; as_of: string } | null;
};

type Summary = { gravida: number; para: number; aborto: number };

const emptyForm = { lmp_date: "", ultrasound_due_date: "", ultrasound_date: "", notes: "", status: "active" };

export function PregnancyView({
  patientId,
  episodes: initialEpisodes,
  summary: initialSummary,
  initialAsOf,
}: {
  patientId: string;
  episodes: Episode[];
  summary: Summary;
  initialAsOf: string;
}) {
  const t = useTranslations("Pregnancy");
  const locale = useLocale();
  const router = useRouter();

  const [episodes, setEpisodes] = useState<Episode[]>(initialEpisodes);
  const [summary, setSummary] = useState<Summary>(initialSummary);
  const [asOf, setAsOf] = useState(initialAsOf);
  const [pending, startTransition] = useTransition();
  const [showAdd, setShowAdd] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [error, setError] = useState("");

  // IG is recomputed on the server for the explicit reference date: the client
  // never assumes "today" and never derives the age itself.
  async function reload(date: string) {
    const [list, gop] = await Promise.all([
      getPregnancies(patientId, date),
      getObstetricSummary(patientId),
    ]);
    setEpisodes(list as Episode[]);
    setSummary(gop);
  }

  function onAsOfChange(value: string) {
    setAsOf(value);
    if (!value) return;
    startTransition(() => {
      void reload(value);
    });
  }

  function resetForm() {
    setForm({ ...emptyForm });
    setError("");
  }

  function payload() {
    const body: Record<string, unknown> = {};
    if (form.lmp_date) body.lmp_date = form.lmp_date;
    if (form.ultrasound_due_date) body.ultrasound_due_date = form.ultrasound_due_date;
    if (form.ultrasound_date) body.ultrasound_date = form.ultrasound_date;
    if (form.notes) body.notes = form.notes;
    return body;
  }

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        await createPregnancy(patientId, { ...payload(), status: form.status });
        await reload(asOf);
        resetForm();
        setShowAdd(false);
        router.refresh();
      } catch {
        setError(t("None"));
      }
    });
  }

  function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!editingId) return;
    setError("");
    startTransition(async () => {
      try {
        await updatePregnancy(editingId, { ...payload(), status: form.status });
        await reload(asOf);
        setEditingId(null);
        resetForm();
        router.refresh();
      } catch {
        setError(t("None"));
      }
    });
  }

  function handleDelete(id: string) {
    startTransition(async () => {
      await deletePregnancy(id);
      await reload(asOf);
      router.refresh();
    });
  }

  function startEdit(ep: Episode) {
    setEditingId(ep.id);
    setShowAdd(false);
    setError("");
    setForm({
      lmp_date: ep.lmp_date ?? "",
      ultrasound_due_date: ep.ultrasound_due_date ?? "",
      ultrasound_date: ep.ultrasound_date ?? "",
      notes: ep.notes ?? "",
      status: ep.status,
    });
  }

  const gaText = (ep: Episode) => {
    const ga = ep.gestational_age;
    if (!ga) return t("NoDate");
    return `${ga.weeks}${t("Weeks")} ${ga.days}${t("Days")}`;
  };

  return (
    <div className="space-y-6">
      {/* Derived GOP + reference date */}
      <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border bg-card p-4 sm:p-5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("Gop")}</span>
          <span className="text-sm font-medium">{t("Gravida")}: {summary.gravida}</span>
          <span className="text-sm font-medium">{t("Para")}: {summary.para}</span>
          <span className="text-sm font-medium">{t("Aborto")}: {summary.aborto}</span>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <CalendarClock className="size-4 text-muted-foreground" />
          <span className="text-muted-foreground">{t("GestationalAge")}</span>
          <input
            type="date"
            value={asOf}
            onChange={(e) => onAsOfChange(e.target.value)}
            className={inputCls + " w-auto"}
          />
        </label>
      </div>

      <p className="text-xs text-muted-foreground">{t("Note")}</p>

      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{t("Title")}</h3>
        <button
          onClick={() => {
            resetForm();
            setEditingId(null);
            setShowAdd((v) => !v);
          }}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="size-4" />
          {t("Add")}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div>
      )}

      {(showAdd || editingId) && (
        <EpisodeForm
          t={t}
          form={form}
          setForm={setForm}
          pending={pending}
          onCancel={() => {
            resetForm();
            setShowAdd(false);
            setEditingId(null);
          }}
          onSubmit={editingId ? handleUpdate : handleCreate}
        />
      )}

      {episodes.length === 0 ? (
        <div className="rounded-2xl border bg-card py-12 text-center text-muted-foreground">{t("None")}</div>
      ) : (
        <ul className="space-y-3">
          {episodes.map((ep) => (
            <li key={ep.id} className="rounded-2xl border bg-card p-4 sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-pink-500/10 text-pink-600 dark:text-pink-400">
                    <Baby className="size-5" />
                  </span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[ep.status] ?? "bg-muted text-muted-foreground"}`}>
                        {t(`Status_${ep.status}`)}
                      </span>
                      <span className="text-sm font-medium">
                        {t("GestationalAge")}: {gaText(ep)}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t("LmpDate")}: {formatDate(ep.lmp_date, locale)} · {t("DueDate")}: {formatDate(ep.estimated_due_date, locale)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => startEdit(ep)}
                    title={t("Save")}
                    aria-label={t("Save")}
                    className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
                  >
                    <Pencil className="size-3.5" />
                  </button>
                  <button
                    onClick={() => handleDelete(ep.id)}
                    disabled={pending}
                    title={t("Delete")}
                    aria-label={t("Delete")}
                    className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>

              {(ep.ultrasound_due_date || ep.ultrasound_date || ep.ended_at || ep.notes) && (
                <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 border-t pt-3 text-xs sm:grid-cols-4">
                  {ep.ultrasound_due_date && (
                    <Meta label={t("UltrasoundDueDate")} value={formatDate(ep.ultrasound_due_date, locale)} />
                  )}
                  {ep.ultrasound_date && (
                    <Meta label={t("UltrasoundDate")} value={formatDate(ep.ultrasound_date, locale)} />
                  )}
                  {ep.ended_at && <Meta label={t("EndedAt")} value={formatDate(ep.ended_at, locale)} />}
                  {ep.notes && <Meta label={t("Notes")} value={ep.notes} />}
                </dl>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}

function EpisodeForm({
  t,
  form,
  setForm,
  pending,
  onCancel,
  onSubmit,
}: {
  t: (key: string) => string;
  form: { lmp_date: string; ultrasound_due_date: string; ultrasound_date: string; notes: string; status: string };
  setForm: (f: any) => void;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  const tc = useTranslations("Common");
  return (
    <form onSubmit={onSubmit} className="rounded-2xl border bg-card p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm font-semibold">{t("NewEpisode")}</span>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("LmpDate")}</span>
          <input
            type="date"
            value={form.lmp_date}
            onChange={(e) => setForm({ ...form, lmp_date: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("Status")}</span>
          <select
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}
            className={inputCls}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{t(`Status_${s}`)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("UltrasoundDueDate")}</span>
          <input
            type="date"
            value={form.ultrasound_due_date}
            onChange={(e) => setForm({ ...form, ultrasound_due_date: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("UltrasoundDate")}</span>
          <input
            type="date"
            value={form.ultrasound_date}
            onChange={(e) => setForm({ ...form, ultrasound_date: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm sm:col-span-2">
          <span className="font-medium">{t("Notes")}</span>
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={2}
            className={inputCls}
          />
        </label>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {t("Save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
        >
          {tc("Cancel")}
        </button>
      </div>
    </form>
  );
}
