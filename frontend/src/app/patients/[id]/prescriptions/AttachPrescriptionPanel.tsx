"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { FileUp, Loader2 } from "lucide-react";
import { attachPrescription } from "@/lib/api";

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

/**
 * Anexa uma receita em PDF emitida FORA do OpenAvisio (ex.: baixada do site da
 * Memed) ao prontuário do paciente. O backend arquiva criptografada por
 * paciente e ela aparece na lista imediatamente após o sucesso.
 */
export function AttachPrescriptionPanel({ patientId }: { patientId: string }) {
  const router = useRouter();
  const t = useTranslations("Prescriptions");
  const tc = useTranslations("Common");
  const [pending, startTransition] = useTransition();
  const [file, setFile] = useState<File | null>(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null);
    setNotes("");
    setError("");
    setSuccess(false);
    if (inputRef.current) inputRef.current.value = "";
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);

    if (!file) {
      setError(t("AttachSelectFile"));
      return;
    }
    const isPdf =
      file.type === "application/pdf" ||
      file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      setError(t("AttachNotPdf"));
      return;
    }

    startTransition(async () => {
      try {
        await attachPrescription(patientId, file, { notes: notes || undefined });
        reset();
        setSuccess(true);
        router.refresh();
      } catch {
        setError(t("AttachError"));
      }
    });
  }

  return (
    <div className="mb-6 rounded-xl border bg-card p-4">
      <div className="mb-1 text-sm font-semibold">{t("AttachTitle")}</div>
      <p className="mb-4 text-xs text-muted-foreground">{t("AttachHint")}</p>

      {error && (
        <div className="mb-4 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 px-4 py-3 text-sm">
          {t("AttachSuccess")}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">{t("AttachFile")}</label>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,application/pdf"
            data-testid="attach-prescription-file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">{t("AttachNotes")}</label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className={inputCls}
          />
        </div>

        <div className="flex items-center gap-3 pt-1">
          <button
            type="submit"
            disabled={pending}
            data-testid="attach-prescription-submit"
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {pending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileUp className="size-4" />
            )}
            {pending ? t("Attaching") : t("AttachSubmit")}
          </button>
          <button
            type="button"
            onClick={reset}
            disabled={pending}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            {tc("Cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}
