"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { formatDate } from "@/lib/utils";
import {
  getPregnancies,
  getPregnancy,
  getObstetricSummary,
  createPregnancy,
  updatePregnancy,
  deletePregnancy,
  getPregnancyVisits,
  createPregnancyVisit,
  updatePregnancyVisit,
  deletePregnancyVisit,
  registerPregnancyOutcome,
  addPregnancyCondition,
  removePregnancyCondition,
  linkPregnancyResource,
  unlinkPregnancyResource,
  getObservations,
  getDocuments,
} from "@/lib/api";
import { Baby, Plus, X, Trash2, Pencil, CalendarClock, ChevronDown, ChevronRight, Link2 } from "lucide-react";

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

// Complete outcome taxonomy (OB-DEC-3): deliveries carry newborn data, losses do not.
const OUTCOME_TYPES = [
  "vaginal_delivery",
  "cesarean_delivery",
  "miscarriage",
  "induced_abortion",
  "ectopic",
  "fetal_death",
] as const;
const DELIVERY_TYPES: readonly string[] = ["vaginal_delivery", "cesarean_delivery"];
const NEWBORN_SEXES = ["female", "male", "unknown"] as const;

const PRESENTATIONS = ["cephalic", "breech", "transverse", "oblique", "variable", "not_assessed"] as const;
const EDEMA_GRADES = ["none", "mild", "moderate", "severe"] as const;
const PROTEINURIA_GRADES = ["negative", "trace", "plus1", "plus2", "plus3", "plus4"] as const;

type Episode = {
  id: string;
  status: string;
  lmp_date: string | null;
  estimated_due_date: string | null;
  ultrasound_due_date: string | null;
  ultrasound_date: string | null;
  ended_at: string | null;
  notes: string | null;
  visit_count?: number;
  gestational_age?: { weeks: number; days: number; basis: string; as_of: string } | null;
  outcome?: Outcome | null;
  // OB-4 clinical integrations.
  condition_count?: number;
  vital_count?: number;
  exam_count?: number;
  conditions?: ConditionLink[];
  vitals?: VitalObs[];
  exams?: ExamDoc[];
};

// An intercorrência at the problem list (Condition), with its CID-10 snapshot.
type ConditionLink = {
  condition_id: string;
  cid10_code: string | null;
  cid10_display: string | null;
};

// A vital (Observation) attributed to the episode.
type VitalObs = {
  id: string;
  code: string | null;
  code_display: string | null;
  value_quantity: number | null;
  value_unit: string | null;
  effective_date_time: string | null;
};

// An exam (document) attributed to the episode.
type ExamDoc = {
  id: string;
  type: string | null;
  description: string | null;
  file_name: string | null;
  issued_date: string | null;
};

type Outcome = {
  id: string;
  pregnancy_id: string;
  outcome_type: string;
  outcome_date: string;
  newborn_weight_g: number | null;
  apgar_1: number | null;
  apgar_5: number | null;
  newborn_sex: string | null;
  notes: string | null;
  gestational_age?: { weeks: number; days: number; basis: string; as_of: string } | null;
};

type Visit = {
  id: string;
  pregnancy_id: string;
  visit_date: string;
  fundal_height_cm: number | null;
  fetal_heart_rate_bpm: number | null;
  presentation: string | null;
  edema: string | null;
  proteinuria: string | null;
  notes: string | null;
  gestational_age?: { weeks: number; days: number; basis: string; as_of: string } | null;
};

type Summary = { gravida: number; para: number; aborto: number };

const emptyForm = { lmp_date: "", ultrasound_due_date: "", ultrasound_date: "", notes: "", status: "active" };
const emptyVisitForm = {
  visit_date: "",
  fundal_height_cm: "",
  fetal_heart_rate_bpm: "",
  presentation: "",
  edema: "",
  proteinuria: "",
  notes: "",
};

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

  const gaText = (ga: Visit["gestational_age"] | Episode["gestational_age"]) => {
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
                        {t("GestationalAge")}: {gaText(ep.gestational_age)}
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

              {/* Prenatal visits — dated obstetric records of this episode (OB-2). */}
              <VisitTimeline
                patientId={patientId}
                episodeId={ep.id}
                initialCount={ep.visit_count ?? 0}
                onCountChange={(count) =>
                  setEpisodes((prev) =>
                    prev.map((e) => (e.id === ep.id ? { ...e, visit_count: count } : e)),
                  )
                }
              />

              {/* Outcome — the dated record that closes the episode (OB-3). */}
              <OutcomeSection
                patientId={patientId}
                episode={ep}
                onRecorded={() => {
                  void reload(asOf);
                  router.refresh();
                }}
              />

              {/* Clinical integrations — intercorrências (Conditions) and the
                  vitals/exams attributed to the episode (OB-4). */}
              <ClinicalIntegrations
                patientId={patientId}
                episode={ep}
                onChanged={() => {
                  void reload(asOf);
                  router.refresh();
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Outcome (OB-3) — registering it CLOSES the episode. Newborn fields are only
// shown/accepted for a live birth; the GA shown is the server-computed age on
// the outcome's own date (the client never substitutes "today").
function OutcomeSection({
  patientId,
  episode,
  onRecorded,
}: {
  patientId: string;
  episode: Episode;
  onRecorded: () => void;
}) {
  const t = useTranslations("Pregnancy");
  const tc = useTranslations("Common");
  const locale = useLocale();
  const [showForm, setShowForm] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    outcome_type: "vaginal_delivery",
    outcome_date: "",
    newborn_weight_g: "",
    apgar_1: "",
    apgar_5: "",
    newborn_sex: "",
    notes: "",
  });

  const outcome = episode.outcome;
  const isDeliveryType = (type: string) => DELIVERY_TYPES.includes(type);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.outcome_date) return;
    setError("");
    startTransition(async () => {
      try {
        const body: Record<string, unknown> = {
          outcome_type: form.outcome_type,
          outcome_date: form.outcome_date,
        };
        if (isDeliveryType(form.outcome_type)) {
          if (form.newborn_weight_g) body.newborn_weight_g = Number(form.newborn_weight_g);
          if (form.apgar_1) body.apgar_1 = Number(form.apgar_1);
          if (form.apgar_5) body.apgar_5 = Number(form.apgar_5);
          if (form.newborn_sex) body.newborn_sex = form.newborn_sex;
        }
        if (form.notes) body.notes = form.notes;
        await registerPregnancyOutcome(patientId, episode.id, body);
        setShowForm(false);
        onRecorded();
      } catch {
        setError(t("None"));
      }
    });
  }

  const gaText = (ga?: Outcome["gestational_age"] | null) => {
    if (!ga) return t("NoDate");
    return `${ga.weeks}${t("Weeks")} ${ga.days}${t("Days")}`;
  };

  const showNewborn =
    outcome != null &&
    isDeliveryType(outcome.outcome_type) &&
    (outcome.newborn_weight_g != null ||
      outcome.apgar_1 != null ||
      outcome.apgar_5 != null ||
      outcome.newborn_sex != null);

  return (
    <div className="mt-3 border-t pt-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("Outcome")}
        </span>
        {!outcome && (
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
          >
            <Plus className="size-3.5" />
            {t("OutcomeRegister")}
          </button>
        )}
      </div>

      {error && (
        <div className="mt-2 rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>
      )}

      {!outcome && showForm && (
        <form onSubmit={submit} className="mt-3 rounded-xl border bg-muted/20 p-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">{t("OutcomeType")}</span>
              <select
                value={form.outcome_type}
                onChange={(e) => setForm({ ...form, outcome_type: e.target.value })}
                className={inputCls}
              >
                {OUTCOME_TYPES.map((o) => (
                  <option key={o} value={o}>
                    {t(`Outcome_${o}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1.5 text-sm">
              <span className="font-medium">{t("OutcomeDate")}</span>
              <input
                type="date"
                required
                value={form.outcome_date}
                onChange={(e) => setForm({ ...form, outcome_date: e.target.value })}
                className={inputCls}
              />
            </label>
          </div>
          {isDeliveryType(form.outcome_type) && (
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">{t("NewbornWeight")}</span>
                <input
                  type="number"
                  value={form.newborn_weight_g}
                  onChange={(e) => setForm({ ...form, newborn_weight_g: e.target.value })}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">{t("Apgar1")}</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={form.apgar_1}
                  onChange={(e) => setForm({ ...form, apgar_1: e.target.value })}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">{t("Apgar5")}</span>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={form.apgar_5}
                  onChange={(e) => setForm({ ...form, apgar_5: e.target.value })}
                  className={inputCls}
                />
              </label>
              <label className="space-y-1.5 text-sm">
                <span className="font-medium">{t("NewbornSex")}</span>
                <select
                  value={form.newborn_sex}
                  onChange={(e) => setForm({ ...form, newborn_sex: e.target.value })}
                  className={inputCls}
                >
                  <option value="">{t("NoDate")}</option>
                  {NEWBORN_SEXES.map((s) => (
                    <option key={s} value={s}>
                      {t(`Sex_${s}`)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <label className="mt-3 block space-y-1.5 text-sm">
            <span className="font-medium">{t("Notes")}</span>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={2}
              className={inputCls}
            />
          </label>
          <div className="mt-3 flex items-center gap-3">
            <button
              type="submit"
              disabled={pending}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {t("Save")}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
            >
              {tc("Cancel")}
            </button>
          </div>
        </form>
      )}

      {outcome && (
        <div className="mt-2 rounded-xl border bg-background p-3">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <span className="text-sm font-medium">{t(`Outcome_${outcome.outcome_type}`)}</span>
            <span className="text-xs text-muted-foreground">{formatDate(outcome.outcome_date, locale)}</span>
            <span className="text-xs text-muted-foreground">
              {t("OutcomeGA")}: {gaText(outcome.gestational_age)}
            </span>
          </div>
          {showNewborn && (
            <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
              {outcome!.newborn_weight_g != null && (
                <span>
                  {t("NewbornWeight")}: {outcome!.newborn_weight_g}
                </span>
              )}
              {outcome!.apgar_1 != null && (
                <span>
                  {t("Apgar1")}: {outcome!.apgar_1}
                </span>
              )}
              {outcome!.apgar_5 != null && (
                <span>
                  {t("Apgar5")}: {outcome!.apgar_5}
                </span>
              )}
              {outcome!.newborn_sex && (
                <span>
                  {t("NewbornSex")}: {t(`Sex_${outcome!.newborn_sex}`)}
                </span>
              )}
            </div>
          )}
          {outcome.notes && <p className="mt-1 text-xs text-foreground">{outcome.notes}</p>}
        </div>
      )}
    </div>
  );
}

// OB-4 — the episode's clinical integrations. Intercorrências are linked to the
// problem list as Conditions (found-or-created server-side by patient + code, so
// the same diagnosis never duplicates); vitals and exams are attributed to the
// episode. Every mutating call returns the updated episode, which re-seeds the
// local lists; the parent is told so it refreshes the counts.
function ClinicalIntegrations({
  patientId,
  episode,
  onChanged,
}: {
  patientId: string;
  episode: Episode;
  onChanged: () => void;
}) {
  const t = useTranslations("Pregnancy");
  const tc = useTranslations("Common");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [conditions, setConditions] = useState<ConditionLink[]>(episode.conditions ?? []);
  const [vitals, setVitals] = useState<VitalObs[]>(episode.vitals ?? []);
  const [exams, setExams] = useState<ExamDoc[]>(episode.exams ?? []);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  const [showCond, setShowCond] = useState(false);
  const [condForm, setCondForm] = useState({ cid10_code: "", cid10_display: "" });

  const [pickVital, setPickVital] = useState(false);
  const [pickExam, setPickExam] = useState(false);
  const [obsOptions, setObsOptions] = useState<VitalObs[] | null>(null);
  const [docOptions, setDocOptions] = useState<ExamDoc[] | null>(null);
  const [chosenVital, setChosenVital] = useState("");
  const [chosenExam, setChosenExam] = useState("");

  function apply(ep: Episode) {
    setConditions(ep.conditions ?? []);
    setVitals(ep.vitals ?? []);
    setExams(ep.exams ?? []);
    onChanged();
  }

  function run(fn: () => Promise<Episode>) {
    setError("");
    startTransition(async () => {
      try {
        apply(await fn());
      } catch {
        setError(t("None"));
      }
    });
  }

  function addCondition(e: React.FormEvent) {
    e.preventDefault();
    if (!condForm.cid10_code && !condForm.cid10_display) return;
    run(async () => {
      const ep = await addPregnancyCondition(patientId, episode.id, {
        cid10_code: condForm.cid10_code || null,
        cid10_display: condForm.cid10_display || null,
      });
      setCondForm({ cid10_code: "", cid10_display: "" });
      setShowCond(false);
      return ep;
    });
  }

  function removeCondition(conditionId: string) {
    setError("");
    startTransition(async () => {
      try {
        await removePregnancyCondition(patientId, episode.id, conditionId);
        // DELETE returns 204 (no body): re-read the episode for the new lists.
        apply(await getPregnancy(episode.id));
      } catch {
        setError(t("None"));
      }
    });
  }

  function openVitalPicker() {
    setPickVital(true);
    if (obsOptions === null) {
      startTransition(async () => {
        const all = (await getObservations(patientId, { category: "measurement" })) as VitalObs[];
        const linked = new Set(vitals.map((v) => v.id));
        setObsOptions(all.filter((o) => !linked.has(o.id)));
      });
    }
  }

  function openExamPicker() {
    setPickExam(true);
    if (docOptions === null) {
      startTransition(async () => {
        const all = (await getDocuments(patientId)) as ExamDoc[];
        const linked = new Set(exams.map((x) => x.id));
        setDocOptions(all.filter((d) => !linked.has(d.id)));
      });
    }
  }

  const vitalLabel = (v: VitalObs) => v.code_display || v.code || v.id.slice(0, 8);
  const examLabel = (d: ExamDoc) => d.description || d.file_name || d.type || d.id.slice(0, 8);

  return (
    <div className="mt-3 border-t pt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
        {t("Integrations")} ({conditions.length + vitals.length + exams.length})
      </button>

      {open && (
        <div className="mt-3 space-y-4">
          {error && (
            <div className="rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>
          )}

          {/* Intercorrências (linked Conditions). */}
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("Intercorrences")} ({conditions.length})
              </span>
              <button
                type="button"
                onClick={() => setShowCond((v) => !v)}
                className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Plus className="size-3.5" />
                {t("AddIntercorrence")}
              </button>
            </div>

            {showCond && (
              <form onSubmit={addCondition} className="mt-2 flex flex-wrap items-end gap-2 rounded-xl border bg-muted/20 p-3">
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">{t("Cid10Code")}</span>
                  <input
                    value={condForm.cid10_code}
                    onChange={(e) => setCondForm({ ...condForm, cid10_code: e.target.value })}
                    className={inputCls + " w-32"}
                  />
                </label>
                <label className="space-y-1.5 text-sm">
                  <span className="font-medium">{t("Cid10Display")}</span>
                  <input
                    value={condForm.cid10_display}
                    onChange={(e) => setCondForm({ ...condForm, cid10_display: e.target.value })}
                    className={inputCls + " w-64"}
                  />
                </label>
                <button
                  type="submit"
                  disabled={pending}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {t("Save")}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCond(false)}
                  className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
                >
                  {tc("Cancel")}
                </button>
              </form>
            )}

            {conditions.length === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">{t("IntercorrencesNone")}</p>
            ) : (
              <ul className="mt-2 flex flex-wrap gap-2">
                {conditions.map((c) => (
                  <li
                    key={c.condition_id}
                    className="inline-flex items-center gap-2 rounded-full border bg-background px-3 py-1 text-xs"
                  >
                    {c.cid10_code && <span className="font-semibold">{c.cid10_code}</span>}
                    <span>{c.cid10_display || t("NoDate")}</span>
                    <button
                      type="button"
                      onClick={() => removeCondition(c.condition_id)}
                      disabled={pending}
                      aria-label={t("Delete")}
                      className="text-destructive hover:opacity-70 disabled:opacity-50"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Linked exams (DocumentReferences). */}
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("Exams")} ({exams.length})
              </span>
              <button
                type="button"
                onClick={openExamPicker}
                className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Link2 className="size-3.5" />
                {t("LinkExisting")}
              </button>
            </div>
            {pickExam && (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-3">
                <select
                  value={chosenExam}
                  onChange={(e) => setChosenExam(e.target.value)}
                  className={inputCls + " w-72"}
                >
                  <option value="">{t("SelectExam")}</option>
                  {(docOptions ?? []).map((d) => (
                    <option key={d.id} value={d.id}>
                      {examLabel(d)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={pending || !chosenExam}
                  onClick={() =>
                    run(async () => {
                      const ep = await linkPregnancyResource(patientId, episode.id, { document_id: chosenExam });
                      setChosenExam("");
                      setPickExam(false);
                      setDocOptions(null);
                      return ep;
                    })
                  }
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {t("Save")}
                </button>
                <button type="button" onClick={() => setPickExam(false)} className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
                  {tc("Cancel")}
                </button>
              </div>
            )}
            {exams.length === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">{t("ExamsNone")}</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {exams.map((d) => (
                  <li key={d.id} className="flex items-center justify-between rounded-lg border bg-background px-3 py-1.5 text-xs">
                    <span>
                      <span className="font-medium">{d.description || d.file_name || d.type || d.id.slice(0, 8)}</span>
                      {d.issued_date && <span className="ml-2 text-muted-foreground">{formatDate(d.issued_date, locale)}</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        run(async () =>
                          unlinkPregnancyResource(patientId, episode.id, { document_id: d.id }),
                        )
                      }
                      disabled={pending}
                      aria-label={t("Delete")}
                      className="text-destructive hover:opacity-70 disabled:opacity-50"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Linked vitals (Observations, category=measurement). */}
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {t("Vitals")} ({vitals.length})
              </span>
              <button
                type="button"
                onClick={openVitalPicker}
                className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
              >
                <Link2 className="size-3.5" />
                {t("LinkExisting")}
              </button>
            </div>
            {pickVital && (
              <div className="mt-2 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 p-3">
                <select
                  value={chosenVital}
                  onChange={(e) => setChosenVital(e.target.value)}
                  className={inputCls + " w-72"}
                >
                  <option value="">{t("SelectVital")}</option>
                  {(obsOptions ?? []).map((o) => (
                    <option key={o.id} value={o.id}>
                      {vitalLabel(o)}
                      {o.value_quantity != null ? ` — ${o.value_quantity}${o.value_unit ? ` ${o.value_unit}` : ""}` : ""}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={pending || !chosenVital}
                  onClick={() =>
                    run(async () => {
                      const ep = await linkPregnancyResource(patientId, episode.id, { observation_id: chosenVital });
                      setChosenVital("");
                      setPickVital(false);
                      setObsOptions(null);
                      return ep;
                    })
                  }
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {t("Save")}
                </button>
                <button type="button" onClick={() => setPickVital(false)} className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors">
                  {tc("Cancel")}
                </button>
              </div>
            )}
            {vitals.length === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">{t("VitalsNone")}</p>
            ) : (
              <ul className="mt-2 space-y-1">
                {vitals.map((o) => (
                  <li key={o.id} className="flex items-center justify-between rounded-lg border bg-background px-3 py-1.5 text-xs">
                    <span>
                      <span className="font-medium">{vitalLabel(o)}</span>
                      {o.value_quantity != null && (
                        <span className="ml-2 text-muted-foreground">
                          {o.value_quantity}
                          {o.value_unit ? ` ${o.value_unit}` : ""}
                        </span>
                      )}
                      {o.effective_date_time && (
                        <span className="ml-2 text-muted-foreground">
                          {formatDate(o.effective_date_time, locale)}
                        </span>
                      )}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        run(async () =>
                          unlinkPregnancyResource(patientId, episode.id, { observation_id: o.id }),
                        )
                      }
                      disabled={pending}
                      aria-label={t("Delete")}
                      className="text-destructive hover:opacity-70 disabled:opacity-50"
                    >
                      <X className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
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

// Gestational age shown for a visit is the server-computed age for the visit's
// own date — the client never derives it and never substitutes "today".
function VisitTimeline({
  patientId,
  episodeId,
  initialCount,
  onCountChange,
}: {
  patientId: string;
  episodeId: string;
  initialCount: number;
  onCountChange: (count: number) => void;
}) {
  const t = useTranslations("Pregnancy");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const [visits, setVisits] = useState<Visit[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ ...emptyVisitForm });
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  async function load() {
    const list = (await getPregnancyVisits(patientId, episodeId)) as Visit[];
    setVisits(list);
    onCountChange(list.length);
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next && visits === null) {
      startTransition(() => {
        void load();
      });
    }
  }

  function resetForm() {
    setForm({ ...emptyVisitForm });
    setError("");
  }

  function payload() {
    const body: Record<string, unknown> = { visit_date: form.visit_date };
    if (form.fundal_height_cm) body.fundal_height_cm = Number(form.fundal_height_cm);
    if (form.fetal_heart_rate_bpm) body.fetal_heart_rate_bpm = Number(form.fetal_heart_rate_bpm);
    if (form.presentation) body.presentation = form.presentation;
    if (form.edema) body.edema = form.edema;
    if (form.proteinuria) body.proteinuria = form.proteinuria;
    if (form.notes) body.notes = form.notes;
    return body;
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.visit_date) return;
    setError("");
    startTransition(async () => {
      try {
        if (editingId) await updatePregnancyVisit(editingId, payload());
        else await createPregnancyVisit(patientId, episodeId, payload());
        await load();
        resetForm();
        setEditingId(null);
        setShowAdd(false);
      } catch {
        setError(t("None"));
      }
    });
  }

  function startEdit(v: Visit) {
    setEditingId(v.id);
    setShowAdd(false);
    setError("");
    setForm({
      visit_date: v.visit_date,
      fundal_height_cm: v.fundal_height_cm != null ? String(v.fundal_height_cm) : "",
      fetal_heart_rate_bpm: v.fetal_heart_rate_bpm != null ? String(v.fetal_heart_rate_bpm) : "",
      presentation: v.presentation ?? "",
      edema: v.edema ?? "",
      proteinuria: v.proteinuria ?? "",
      notes: v.notes ?? "",
    });
  }

  function remove(id: string) {
    startTransition(async () => {
      await deletePregnancyVisit(id);
      await load();
    });
  }

  const count = visits?.length ?? initialCount;
  const gaText = (v: Visit) => {
    const ga = v.gestational_age;
    if (!ga) return t("NoDate");
    return `${ga.weeks}${t("Weeks")} ${ga.days}${t("Days")}`;
  };

  return (
    <div className="mt-3 border-t pt-3">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={toggle}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
          aria-expanded={open}
        >
          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          {t("Visits")} ({count})
        </button>
        {open && (
          <button
            type="button"
            onClick={() => {
              resetForm();
              setEditingId(null);
              setShowAdd((v) => !v);
            }}
            className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
          >
            <Plus className="size-3.5" />
            {t("NewVisit")}
          </button>
        )}
      </div>

      {open && (
        <div className="mt-3 space-y-3">
          {error && (
            <div className="rounded-lg bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>
          )}

          {(showAdd || editingId) && (
            <VisitForm
              t={t}
              form={form}
              setForm={setForm}
              pending={pending}
              onCancel={() => {
                resetForm();
                setShowAdd(false);
                setEditingId(null);
              }}
              onSubmit={submit}
            />
          )}

          {visits === null ? (
            <div className="py-3 text-center text-sm text-muted-foreground">…</div>
          ) : visits.length === 0 ? (
            <div className="rounded-xl border bg-muted/30 py-6 text-center text-sm text-muted-foreground">
              {t("VisitsNone")}
            </div>
          ) : (
            <ol className="relative space-y-2 border-l pl-4">
              {visits.map((v) => (
                <li key={v.id} className="relative">
                  <span className="absolute -left-[21px] top-2 size-2 rounded-full bg-pink-500" />
                  <div className="rounded-xl border bg-background p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium">{formatDate(v.visit_date, locale)}</span>
                          <span className="text-xs text-muted-foreground">
                            {t("GestationalAge")}: {gaText(v)}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                          {v.fundal_height_cm != null && (
                            <span>{t("FundalHeight")}: {v.fundal_height_cm}</span>
                          )}
                          {v.fetal_heart_rate_bpm != null && (
                            <span>{t("FetalHeartRate")}: {v.fetal_heart_rate_bpm}</span>
                          )}
                          {v.presentation && (
                            <span>{t("Presentation")}: {t(`Pres_${v.presentation}`)}</span>
                          )}
                          {v.edema && <span>{t("Edema")}: {t(`Edema_${v.edema}`)}</span>}
                          {v.proteinuria && (
                            <span>{t("Proteinuria")}: {t(`Prot_${v.proteinuria}`)}</span>
                          )}
                        </div>
                        {v.notes && <p className="mt-1 text-xs text-foreground">{v.notes}</p>}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => startEdit(v)}
                          aria-label={t("Save")}
                          className="inline-flex items-center rounded-md border p-1 text-xs hover:bg-muted transition-colors"
                        >
                          <Pencil className="size-3" />
                        </button>
                        <button
                          type="button"
                          onClick={() => remove(v.id)}
                          disabled={pending}
                          aria-label={t("Delete")}
                          className="inline-flex items-center rounded-md border p-1 text-xs text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="size-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

function VisitForm({
  t,
  form,
  setForm,
  pending,
  onCancel,
  onSubmit,
}: {
  t: (key: string) => string;
  form: typeof emptyVisitForm;
  setForm: (f: any) => void;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  const tc = useTranslations("Common");
  return (
    <form onSubmit={onSubmit} className="rounded-xl border bg-muted/20 p-3">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-semibold">{t("NewVisit")}</span>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="size-4" />
        </button>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("VisitDate")}</span>
          <input
            type="date"
            required
            value={form.visit_date}
            onChange={(e) => setForm({ ...form, visit_date: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("FundalHeight")}</span>
          <input
            type="number"
            step="0.1"
            value={form.fundal_height_cm}
            onChange={(e) => setForm({ ...form, fundal_height_cm: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("FetalHeartRate")}</span>
          <input
            type="number"
            value={form.fetal_heart_rate_bpm}
            onChange={(e) => setForm({ ...form, fetal_heart_rate_bpm: e.target.value })}
            className={inputCls}
          />
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("Presentation")}</span>
          <select
            value={form.presentation}
            onChange={(e) => setForm({ ...form, presentation: e.target.value })}
            className={inputCls}
          >
            <option value="">{t("NoDate")}</option>
            {PRESENTATIONS.map((p) => (
              <option key={p} value={p}>{t(`Pres_${p}`)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("Edema")}</span>
          <select
            value={form.edema}
            onChange={(e) => setForm({ ...form, edema: e.target.value })}
            className={inputCls}
          >
            <option value="">{t("NoDate")}</option>
            {EDEMA_GRADES.map((g) => (
              <option key={g} value={g}>{t(`Edema_${g}`)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm">
          <span className="font-medium">{t("Proteinuria")}</span>
          <select
            value={form.proteinuria}
            onChange={(e) => setForm({ ...form, proteinuria: e.target.value })}
            className={inputCls}
          >
            <option value="">{t("NoDate")}</option>
            {PROTEINURIA_GRADES.map((g) => (
              <option key={g} value={g}>{t(`Prot_${g}`)}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1.5 text-sm sm:col-span-3">
          <span className="font-medium">{t("Notes")}</span>
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={2}
            className={inputCls}
          />
        </label>
      </div>
      <div className="mt-3 flex items-center gap-3">
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
