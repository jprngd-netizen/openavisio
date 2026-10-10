"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  linkEncounterPrescription,
  linkEncounterDocument,
  unlinkEncounterPrescription,
  unlinkEncounterDocument,
} from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { Pill, FlaskConical, Plus, X } from "lucide-react";

const inputCls = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const labelCls = "text-sm font-medium";

function prescriptionLabel(rx: any): string {
  const meds = (rx.items ?? [])
    .map((i: any) => i.medication_name)
    .filter(Boolean)
    .join(", ");
  const date = rx.issued_at ? formatDate(rx.issued_at) : formatDate(rx.created_at);
  return meds ? `${date} · ${meds}` : date;
}

function examLabel(doc: any): string {
  return doc.description || doc.file_name || doc.type || formatDate(doc.created_at);
}

/**
 * WS-8: what was prescribed and which exams (lab reports) were linked to this
 * consultation. Lists the linked resources and lets the user attach an existing
 * prescription or exam of the same patient.
 */
export function EncounterLinks({
  encounter,
  prescriptions = [],
  documents = [],
}: {
  encounter: any;
  prescriptions?: any[];
  documents?: any[];
}) {
  const t = useTranslations("Enc");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [showRx, setShowRx] = useState(false);
  const [showExam, setShowExam] = useState(false);
  const [rxChoice, setRxChoice] = useState("");
  const [examChoice, setExamChoice] = useState("");

  const linkedRx: any[] = encounter.prescriptions ?? [];
  const linkedExams: any[] = encounter.exams ?? [];
  const linkedRxIds = new Set(linkedRx.map((r) => r.id));
  const linkedExamIds = new Set(linkedExams.map((e) => e.id));
  const rxCandidates = prescriptions.filter((r) => !linkedRxIds.has(r.id));
  const examCandidates = documents.filter((d) => !linkedExamIds.has(d.id));

  function run(fn: () => Promise<unknown>) {
    setError("");
    startTransition(async () => {
      try {
        await fn();
        router.refresh();
      } catch {
        setError(t("LinkError"));
      }
    });
  }

  function submitRx(e: React.FormEvent) {
    e.preventDefault();
    if (!rxChoice) return;
    run(async () => {
      await linkEncounterPrescription(encounter.id, rxChoice);
      setRxChoice("");
      setShowRx(false);
    });
  }

  function submitExam(e: React.FormEvent) {
    e.preventDefault();
    if (!examChoice) return;
    run(async () => {
      await linkEncounterDocument(encounter.id, examChoice);
      setExamChoice("");
      setShowExam(false);
    });
  }

  return (
    <div className="mt-3 space-y-3 border-t pt-3">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-3 py-2 text-xs">{error}</div>
      )}

      {/* Prescriptions issued in this consultation */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <Pill className="h-4 w-4 text-muted-foreground" />
            <span className={labelCls}>{t("PrescriptionsSection")}</span>
          </div>
          {rxCandidates.length > 0 && (
            <button
              type="button"
              onClick={() => setShowRx((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("LinkPrescription")}
            </button>
          )}
        </div>

        {linkedRx.length === 0 && <p className="text-xs text-muted-foreground">{t("PrescriptionsLinkedEmpty")}</p>}
        {linkedRx.map((r) => (
          <div key={r.id} className="flex items-center justify-between gap-2 rounded-lg border bg-card px-3 py-2">
            <div className="min-w-0">
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs uppercase text-muted-foreground">{r.status}</span>
              <span className="ml-2 text-sm">{prescriptionLabel(r)}</span>
            </div>
            <button
              type="button"
              onClick={() => run(() => unlinkEncounterPrescription(encounter.id, r.id))}
              disabled={pending}
              title={t("Unlink")}
              className="inline-flex shrink-0 items-center justify-center rounded-md border px-2 py-1 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}

        {showRx && (
          <form onSubmit={submitRx} className="flex items-center gap-2 rounded-lg border bg-muted/30 p-3">
            <select value={rxChoice} onChange={(e) => setRxChoice(e.target.value)} className={inputCls}>
              <option value="">{t("SelectPrescription")}</option>
              {rxCandidates.map((r) => (
                <option key={r.id} value={r.id}>{prescriptionLabel(r)}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={pending || !rxChoice}
              className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {pending ? t("Linking") : t("LinkSave")}
            </button>
          </form>
        )}
      </div>

      {/* Linked exams */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            <span className={labelCls}>{t("ExamsSection")}</span>
          </div>
          {examCandidates.length > 0 && (
            <button
              type="button"
              onClick={() => setShowExam((v) => !v)}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              <Plus className="h-3.5 w-3.5" />
              {t("LinkExam")}
            </button>
          )}
        </div>

        {linkedExams.length === 0 && <p className="text-xs text-muted-foreground">{t("ExamsLinkedEmpty")}</p>}
        {linkedExams.map((d) => (
          <div key={d.id} className="flex items-center justify-between gap-2 rounded-lg border bg-card px-3 py-2">
            <div className="min-w-0">
              <span className="text-sm">{examLabel(d)}</span>
              {d.issued_date && <span className="ml-2 text-xs text-muted-foreground">{formatDate(d.issued_date)}</span>}
            </div>
            <button
              type="button"
              onClick={() => run(() => unlinkEncounterDocument(encounter.id, d.id))}
              disabled={pending}
              title={t("Unlink")}
              className="inline-flex shrink-0 items-center justify-center rounded-md border px-2 py-1 text-muted-foreground transition-colors hover:border-destructive hover:text-destructive disabled:opacity-50"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}

        {showExam && (
          <form onSubmit={submitExam} className="flex items-center gap-2 rounded-lg border bg-muted/30 p-3">
            <select value={examChoice} onChange={(e) => setExamChoice(e.target.value)} className={inputCls}>
              <option value="">{t("SelectExam")}</option>
              {examCandidates.map((d) => (
                <option key={d.id} value={d.id}>{examLabel(d)}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={pending || !examChoice}
              className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {pending ? t("Linking") : t("LinkSave")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
