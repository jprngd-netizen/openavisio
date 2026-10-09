"use client";

import { useTranslations } from "next-intl";
import { formatDate } from "@/lib/utils";
import { AlertTriangle, Pill } from "lucide-react";

/**
 * "Medicações ativas agora" (WS-2) — the active-medication reconciliation view.
 *
 * Lists every medication that is active and currently in force, straight from
 * GET /medications/active. A row whose `duplicate_of` is non-empty shares a
 * substance with another active medication, so it is highlighted as a possible
 * double prescription. v1 flags duplicates only (DEC-2: no interaction check).
 */
export function ActiveMedicationsPanel({ medications }: { medications: any[] }) {
  const t = useTranslations("Enc");
  const duplicates = medications.filter((m: any) => (m.duplicate_of ?? []).length > 0).length;

  return (
    <div className="rounded-xl border bg-card p-4 mb-6">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Pill className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold">{t("ActiveMedsTitle")}</span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          {medications.length}
        </span>
        {duplicates > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
            <AlertTriangle className="h-3 w-3" />
            {t("ActiveMedsDuplicateCount", { count: duplicates })}
          </span>
        )}
      </div>

      {medications.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("ActiveMedsEmpty")}</p>
      ) : (
        <ul className="space-y-2">
          {medications.map((m: any) => {
            const dup = (m.duplicate_of ?? []).length > 0;
            const period = [
              m.effective_start ? t("ActiveMedsSince", { date: formatDate(m.effective_start) }) : null,
              m.effective_end ? t("ActiveMedsUntil", { date: formatDate(m.effective_end) }) : null,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <li
                key={m.id}
                className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 ${
                  dup ? "border-destructive/50 bg-destructive/5" : "border-border"
                }`}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{m.medication_display}</span>
                    {m.dosage_text && (
                      <span className="text-xs text-muted-foreground">{m.dosage_text}</span>
                    )}
                  </div>
                  {period && <div className="text-xs text-muted-foreground">{period}</div>}
                </div>
                {dup && (
                  <span
                    className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive"
                    title={t("ActiveMedsDuplicateHint")}
                  >
                    <AlertTriangle className="h-3 w-3" />
                    {t("ActiveMedsDuplicateBadge")}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
