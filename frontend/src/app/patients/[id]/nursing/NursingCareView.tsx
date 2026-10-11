"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Save } from "lucide-react";
import { createNursingCare, updateNursingCare, deleteNursingCare } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { NursingStructuredFields } from "./NursingFexeoFields";
import { NursingStructuredSummary } from "./NursingFexeoSummaries";
import {
  SUBCATEGORIES,
  emptyNursingStructured,
  nursingStructuredFromRecord,
  nursingStructuredPayload,
  type NursingStructured,
} from "./fexeoNursingModel";

const inputCls =
  "w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";

// Subcategories that carry a structured instrument subform (I.2/I.3/I.4).
const INSTRUMENT_SUBCATEGORIES = ["labor", "postpartum", "sexual_reproductive"] as const;

// The instant, in the Brazil offset the API serializes (…-03:00): the date part
// is a calendar date and the time part is its local wall clock. Slicing keeps it
// deterministic (no SSR/client locale mismatch).
function datePart(iso: string): string {
  return iso?.slice(0, 10) ?? "";
}
function timePart(iso: string): string {
  return iso?.slice(11, 16) ?? "";
}
// datetime-local value ("YYYY-MM-DDTHH:MM") from the stored instant.
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16);
}

type Pregnancy = { id: string; lmp_date?: string | null; status?: string };

function pregnancyLabel(p: Pregnancy): string {
  return p.lmp_date ? `${formatDate(p.lmp_date)}` : p.id.slice(0, 8);
}

type Draft = {
  occurred_at: string;
  category: "general" | "obstetric";
  pregnancy_id: string;
  performed_by: string;
  subcategory: string;
  instrument_type: string;
  notes: string;
  structured: NursingStructured;
};

function emptyDraft(): Draft {
  return {
    occurred_at: "",
    category: "general",
    pregnancy_id: "",
    performed_by: "",
    subcategory: "",
    instrument_type: "",
    notes: "",
    structured: emptyNursingStructured(),
  };
}

export function NursingCareView({
  patientId,
  records,
  pregnancies,
}: {
  patientId: string;
  records: any[];
  pregnancies: Pregnancy[];
}) {
  const t = useTranslations("Nursing");
  const [filter, setFilter] = useState<"all" | "general" | "obstetric">("all");

  const shown = filter === "all" ? records : records.filter((r) => r.category === filter);

  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">{t("Note")}</p>

      {/* New record. */}
      <NewRecordForm patientId={patientId} pregnancies={pregnancies} />

      {/* Category filter — the two halves of the approved scope. */}
      <div className="flex flex-wrap items-center gap-2">
        {(["all", "general", "obstetric"] as const).map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => setFilter(c)}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              filter === c ? "border-primary bg-primary text-primary-foreground" : "border-border bg-muted hover:bg-muted/70"
            }`}
          >
            {t(`Category_${c}`)}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {shown.map((r) => (
          <NursingCareRow key={r.id} record={r} pregnancies={pregnancies} />
        ))}
        {shown.length === 0 && <p className="text-sm text-muted-foreground">{t("None")}</p>}
      </div>
    </div>
  );
}

function CategoryBadge({ category }: { category: string }) {
  const t = useTranslations("Nursing");
  const cls =
    category === "obstetric"
      ? "bg-pink-500/10 text-pink-600 dark:text-pink-400"
      : "bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{t(`Category_${category}`)}</span>;
}

// Subcategory selector + instrument type + the conditional structured editor.
function InstrumentFields({
  value,
  onChange,
}: {
  value: Draft;
  onChange: (patch: Partial<Draft>) => void;
}) {
  const t = useTranslations("Nursing");
  const hasInstrument = (INSTRUMENT_SUBCATEGORIES as readonly string[]).includes(value.subcategory);
  return (
    <div className="mt-2 space-y-2">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>{t("Subcategory")}</span>
          <select
            className={inputCls}
            value={value.subcategory}
            onChange={(e) => onChange({ subcategory: e.target.value })}
            aria-label={t("Subcategory")}
          >
            <option value="">{t("SubcategoryNone")}</option>
            {SUBCATEGORIES.map((s) => (
              <option key={s} value={s}>
                {t(`Subcategory_${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs text-muted-foreground">
          <span>{t("InstrumentType")}</span>
          <input
            className={inputCls}
            placeholder={t("InstrumentType")}
            value={value.instrument_type}
            onChange={(e) => onChange({ instrument_type: e.target.value })}
            aria-label={t("InstrumentType")}
          />
        </label>
      </div>
      {hasInstrument && (
        <details className="rounded-lg border bg-muted/20 p-2" open>
          <summary className="cursor-pointer select-none text-xs font-semibold">{t("StructuredData")}</summary>
          <div className="mt-2">
            <NursingStructuredFields
              subcategory={value.subcategory}
              value={value.structured}
              onChange={(patch) => onChange({ structured: { ...value.structured, ...patch } })}
            />
          </div>
        </details>
      )}
    </div>
  );
}

function NewRecordForm({ patientId, pregnancies }: { patientId: string; pregnancies: Pregnancy[] }) {
  const t = useTranslations("Nursing");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState<Draft>(emptyDraft());

  function set(patch: Partial<Draft>) {
    setDraft((d) => ({ ...d, ...patch }));
  }

  function add() {
    if (!draft.occurred_at) return;
    start(async () => {
      await createNursingCare(patientId, {
        occurred_at: draft.occurred_at,
        category: draft.category,
        pregnancy_id: draft.category === "obstetric" && draft.pregnancy_id ? draft.pregnancy_id : null,
        performed_by: draft.performed_by || null,
        subcategory: draft.subcategory || null,
        instrument_type: draft.instrument_type || null,
        structured_data: nursingStructuredPayload(draft.subcategory, draft.structured),
        notes: draft.notes || null,
      });
      setDraft(emptyDraft());
      router.refresh();
    });
  }

  return (
    <section className="rounded-xl border bg-card p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {t("NewRecord")}
      </h3>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-[auto_auto_1fr_auto]">
        <input
          type="datetime-local"
          className={inputCls}
          value={draft.occurred_at}
          onChange={(e) => set({ occurred_at: e.target.value })}
          aria-label={t("OccurredAt")}
          data-testid="nursing-draft-occurred-at"
        />
        <select
          className={inputCls}
          value={draft.category}
          onChange={(e) => set({ category: e.target.value as "general" | "obstetric" })}
          aria-label={t("Category")}
        >
          <option value="general">{t("Category_general")}</option>
          <option value="obstetric">{t("Category_obstetric")}</option>
        </select>
        {draft.category === "obstetric" ? (
          <select
            className={inputCls}
            value={draft.pregnancy_id}
            onChange={(e) => set({ pregnancy_id: e.target.value })}
            aria-label={t("Pregnancy")}
          >
            <option value="">{t("PregnancyNone")}</option>
            {pregnancies.map((p) => (
              <option key={p.id} value={p.id}>{pregnancyLabel(p)}</option>
            ))}
          </select>
        ) : (
          <input
            className={inputCls}
            placeholder={t("PerformedBy")}
            value={draft.performed_by}
            onChange={(e) => set({ performed_by: e.target.value })}
            aria-label={t("PerformedBy")}
          />
        )}
        <button
          type="button"
          onClick={add}
          disabled={pending || !draft.occurred_at}
          className="inline-flex items-center justify-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-60"
        >
          <Plus className="size-4" /> {t("Add")}
        </button>
      </div>
      {draft.category === "obstetric" && (
        <input
          className={`${inputCls} mt-2`}
          placeholder={t("PerformedBy")}
          value={draft.performed_by}
          onChange={(e) => set({ performed_by: e.target.value })}
          aria-label={t("PerformedBy")}
        />
      )}

      {/* FExEO-SUS structured fields (R4) — subcategory / instrument / subform. */}
      <InstrumentFields value={draft} onChange={set} />

      <textarea
        className={`${inputCls} mt-2 min-h-16`}
        placeholder={t("Notes")}
        value={draft.notes}
        onChange={(e) => set({ notes: e.target.value })}
        aria-label={t("Notes")}
        data-testid="nursing-draft-notes"
      />
    </section>
  );
}

function NursingCareRow({ record, pregnancies }: { record: any; pregnancies: Pregnancy[] }) {
  const t = useTranslations("Nursing");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [row, setRow] = useState<Draft>({
    occurred_at: toLocalInput(record.occurred_at),
    category: (record.category ?? "general") as "general" | "obstetric",
    pregnancy_id: record.pregnancy_id ?? "",
    performed_by: record.performed_by ?? "",
    subcategory: record.subcategory ?? "",
    instrument_type: record.instrument_type ?? "",
    notes: record.notes ?? "",
    structured: nursingStructuredFromRecord(record),
  });

  function set(patch: Partial<Draft>) {
    setRow((r) => ({ ...r, ...patch }));
  }

  function save() {
    start(async () => {
      await updateNursingCare(record.id, {
        occurred_at: row.occurred_at || undefined,
        category: row.category,
        pregnancy_id: row.category === "obstetric" ? (row.pregnancy_id || null) : null,
        performed_by: row.performed_by || null,
        subcategory: row.subcategory || null,
        instrument_type: row.instrument_type || null,
        structured_data: nursingStructuredPayload(row.subcategory, row.structured),
        notes: row.notes || null,
      });
      router.refresh();
    });
  }

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <CategoryBadge category={row.category} />
        {row.subcategory && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{t(`Subcategory_${row.subcategory}`)}</span>
        )}
        <span>
          {formatDate(datePart(record.occurred_at))} · {timePart(record.occurred_at)}
        </span>
        {record.pregnancy_id && pregnancies.some((p) => p.id === record.pregnancy_id) && (
          <span>{t("Pregnancy")}: {pregnancyLabel(pregnancies.find((p) => p.id === record.pregnancy_id)!)}</span>
        )}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-[auto_auto_1fr_auto]">
        <input
          type="datetime-local"
          className={inputCls}
          value={row.occurred_at}
          onChange={(e) => set({ occurred_at: e.target.value })}
          aria-label={t("OccurredAt")}
        />
        <select
          className={inputCls}
          value={row.category}
          onChange={(e) => set({ category: e.target.value as "general" | "obstetric" })}
          aria-label={t("Category")}
        >
          <option value="general">{t("Category_general")}</option>
          <option value="obstetric">{t("Category_obstetric")}</option>
        </select>
        {row.category === "obstetric" ? (
          <select
            className={inputCls}
            value={row.pregnancy_id}
            onChange={(e) => set({ pregnancy_id: e.target.value })}
            aria-label={t("Pregnancy")}
          >
            <option value="">{t("PregnancyNone")}</option>
            {pregnancies.map((p) => (
              <option key={p.id} value={p.id}>{pregnancyLabel(p)}</option>
            ))}
          </select>
        ) : (
          <input
            className={inputCls}
            placeholder={t("PerformedBy")}
            value={row.performed_by}
            onChange={(e) => set({ performed_by: e.target.value })}
            aria-label={t("PerformedBy")}
          />
        )}
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={pending}
            onClick={save}
            className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
            aria-label={t("Save")}
          >
            <Save className="size-4" />
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={() => start(async () => { await deleteNursingCare(record.id); router.refresh(); })}
            className="rounded-md p-2 text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
            aria-label={t("Delete")}
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
      {row.category === "obstetric" && (
        <input
          className={`${inputCls} mt-2`}
          placeholder={t("PerformedBy")}
          value={row.performed_by}
          onChange={(e) => set({ performed_by: e.target.value })}
          aria-label={t("PerformedBy")}
        />
      )}

      {/* FExEO-SUS structured fields (R4) — subcategory / instrument / subform. */}
      <InstrumentFields value={row} onChange={set} />

      {/* Read-only projection of what is actually stored (renders after save). */}
      <NursingStructuredSummary record={record} />

      <textarea
        className={`${inputCls} mt-2 min-h-16`}
        placeholder={t("Notes")}
        value={row.notes}
        onChange={(e) => set({ notes: e.target.value })}
        aria-label={t("Notes")}
      />
    </div>
  );
}
