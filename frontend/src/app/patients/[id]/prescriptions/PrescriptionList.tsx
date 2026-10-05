"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { formatDate } from "@/lib/utils";
import { FileSignature, ExternalLink } from "lucide-react";

function statusBadge(status: string, t: (k: string) => string) {
  const label = t(`Status${status.charAt(0).toUpperCase() + status.slice(1)}`);
  const colors: Record<string, string> = {
    draft: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
    issued: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
    failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
    deleted: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
  };
  return (
    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? colors.draft}`}>
      {label}
    </span>
  );
}

export function PrescriptionList({ prescriptions }: { prescriptions: any[] }) {
  const t = useTranslations("Prescriptions");
  const locale = useLocale();
  const [revealed, setRevealed] = useState<string | null>(null);

  return (
    <>
      {/* Mobile: cards */}
      <div className="space-y-3 lg:hidden">
        {prescriptions.map((p: any) => {
          const open = revealed === p.id;
          return (
            <div key={p.id} className={`overflow-hidden rounded-xl border bg-card ${p.status === "deleted" ? "opacity-60" : ""}`}>
              <div className="p-4" onClick={() => setRevealed(open ? null : p.id)}>
                <div className="flex items-start justify-between gap-2">
                  <span className="min-w-0 truncate text-sm font-medium">
                    {p.notes || `Prescription #${p.version}`}
                  </span>
                  {statusBadge(p.status, t)}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {t("CreatedAt")}: {formatDate(p.created_at, locale)}
                  {p.issued_at && <> · {t("IssuedAt")}: {formatDate(p.issued_at, locale)}</>}
                </div>
              </div>
              {open && p.status === "issued" && p.document && (
                <div className="border-t px-4 py-3">
                  <a
                    href={`/api/prescriptions/${p.id}/document`}
                    target="_blank"
                    className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
                  >
                    <ExternalLink className="size-4" />
                    {t("ViewPdf")}
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Desktop: table */}
      <div className="hidden overflow-hidden rounded-xl border bg-card lg:block">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">{t("Notes")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("CreatedAt")}</th>
              <th className="px-4 py-3 text-left font-medium">{t("IssuedAt")}</th>
              <th className="w-px px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y">
            {prescriptions.map((p: any) => (
              <tr key={p.id} className={`hover:bg-muted/30 transition-colors ${p.status === "deleted" ? "opacity-50" : ""}`}>
                <td className="px-4 py-3 font-medium">{p.notes || "—"}</td>
                <td className="px-4 py-3">{statusBadge(p.status, t)}</td>
                <td className="px-4 py-3 text-muted-foreground text-xs">{formatDate(p.created_at, locale)}</td>
                <td className="px-4 py-3 text-muted-foreground text-xs">{p.issued_at ? formatDate(p.issued_at, locale) : "—"}</td>
                <td className="w-px whitespace-nowrap px-4 py-3">
                  {p.status === "issued" && p.document && (
                    <a
                      href={`/api/prescriptions/${p.id}/document`}
                      target="_blank"
                      className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                    >
                      <ExternalLink className="size-3.5" />
                      {t("ViewPdf")}
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}