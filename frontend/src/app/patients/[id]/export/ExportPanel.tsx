"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Printer } from "lucide-react";

// Same order/idiom as the server page. The slug is both the `?sections=` value
// and the `Export.Sections.*` i18n key.
const SECTIONS = [
  "encounters",
  "conditions",
  "medications",
  "measurements",
  "lab-results",
  "documents",
  "prescriptions",
] as const;
type Section = (typeof SECTIONS)[number];

export function ExportPanel({ patientId, selected }: { patientId: string; selected: string[] }) {
  const router = useRouter();
  const t = useTranslations("Export");
  const sel = new Set(selected);
  const allSelected = SECTIONS.every((s) => sel.has(s));

  // Only the checked set is pushed into the URL, so the server re-renders with
  // just those sections. Everything checked = drop the param (its absence means
  // "all"), which keeps the default URL clean.
  function update(next: Section[]) {
    const qs = next.length === SECTIONS.length ? "" : `?sections=${next.join(",")}`;
    router.replace(`/patients/${patientId}/export${qs}`);
  }

  function toggle(slug: Section, checked: boolean) {
    const next = new Set(sel);
    if (checked) next.add(slug);
    else next.delete(slug);
    update(SECTIONS.filter((s) => next.has(s)));
  }

  return (
    <div className="mb-6 rounded-xl border bg-card p-4 print:hidden">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-base font-semibold">{t("Title")}</h1>
          <p className="text-sm text-muted-foreground">{t("Description")}</p>
        </div>
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Printer className="size-4" />
          {t("SavePdf")}
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
        <label className="flex cursor-pointer select-none items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={(e) => update(e.target.checked ? [...SECTIONS] : [])}
          />
          {t("SelectAll")}
        </label>
        {SECTIONS.map((slug) => (
          <label key={slug} className="flex cursor-pointer select-none items-center gap-2 text-sm">
            <input type="checkbox" checked={sel.has(slug)} onChange={(e) => toggle(slug, e.target.checked)} />
            {t(`Sections.${slug}`)}
          </label>
        ))}
      </div>
    </div>
  );
}
