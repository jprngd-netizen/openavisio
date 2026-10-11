"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Save } from "lucide-react";
import { createNursingCare, updateNursingCare, deleteNursingCare } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const inputCls =
  "w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";

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

function NewRecordForm({ patientId, pregnancies }: { patientId: string; pregnancies: Pregnancy[] }) {
  const t = useTranslations("Nursing");
  const router = useRouter();
  const [pending, start] = useTransition();
  const [draft, setDraft] = useState({
    occurred_at: "",
    category: "general" as "general" | "obstetric",
    pregnancy_id: "",
    performed_by: "",
    notes: "",
  });

  function add() {
    if (!draft.occurred_at) return;
    start(async () => {
      await createNursingCare(patientId, {
        occurred_at: draft.occurred_at,
        category: draft.category,
        pregnancy_id: draft.category === "obstetric" && draft.pregnancy_id ? draft.pregnancy_id : null,
        performed_by: draft.performed_by || null,
        notes: draft.notes || null,
      });
      setDraft({ occurred_at: "", category: "general", pregnancy_id: "", performed_by: "", notes: "" });
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
          onChange={(e) => setDraft({ ...draft, occurred_at: e.target.value })}
          aria-label={t("OccurredAt")}
          data-testid="nursing-draft-occurred-at"
        />
        <select
          className={inputCls}
          value={draft.category}
          onChange={(e) => setDraft({ ...draft, category: e.target.value as "general" | "obstetric" })}
          aria-label={t("Category")}
        >
          <option value="general">{t("Category_general")}</option>
          <option value="obstetric">{t("Category_obstetric")}</option>
        </select>
        {draft.category === "obstetric" ? (
          <select
            className={inputCls}
            value={draft.pregnancy_id}
            onChange={(e) => setDraft({ ...draft, pregnancy_id: e.target.value })}
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
            onChange={(e) => setDraft({ ...draft, performed_by: e.target.value })}
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
          onChange={(e) => setDraft({ ...draft, performed_by: e.target.value })}
          aria-label={t("PerformedBy")}
        />
      )}
      <textarea
        className={`${inputCls} mt-2 min-h-16`}
        placeholder={t("Notes")}
        value={draft.notes}
        onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
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
  const [row, setRow] = useState({
    occurred_at: toLocalInput(record.occurred_at),
    category: (record.category ?? "general") as "general" | "obstetric",
    pregnancy_id: record.pregnancy_id ?? "",
    performed_by: record.performed_by ?? "",
    notes: record.notes ?? "",
  });

  function save() {
    start(async () => {
      await updateNursingCare(record.id, {
        occurred_at: row.occurred_at || undefined,
        category: row.category,
        pregnancy_id: row.category === "obstetric" ? (row.pregnancy_id || null) : null,
        performed_by: row.performed_by || null,
        notes: row.notes || null,
      });
      router.refresh();
    });
  }

  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <CategoryBadge category={row.category} />
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
          onChange={(e) => setRow({ ...row, occurred_at: e.target.value })}
          aria-label={t("OccurredAt")}
        />
        <select
          className={inputCls}
          value={row.category}
          onChange={(e) => setRow({ ...row, category: e.target.value as "general" | "obstetric" })}
          aria-label={t("Category")}
        >
          <option value="general">{t("Category_general")}</option>
          <option value="obstetric">{t("Category_obstetric")}</option>
        </select>
        {row.category === "obstetric" ? (
          <select
            className={inputCls}
            value={row.pregnancy_id}
            onChange={(e) => setRow({ ...row, pregnancy_id: e.target.value })}
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
            onChange={(e) => setRow({ ...row, performed_by: e.target.value })}
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
          onChange={(e) => setRow({ ...row, performed_by: e.target.value })}
          aria-label={t("PerformedBy")}
        />
      )}
      <textarea
        className={`${inputCls} mt-2 min-h-16`}
        placeholder={t("Notes")}
        value={row.notes}
        onChange={(e) => setRow({ ...row, notes: e.target.value })}
        aria-label={t("Notes")}
      />
    </div>
  );
}
