import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient } from "@/lib/api";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { ChevronRight, Printer } from "lucide-react";
import { OCCUPATIONAL_SECTIONS, OCCUPATIONAL_PRINT_ITEM } from "@/lib/occupationalSections";

// Index of the "Prontuário Ocupacional" — the grouped taxonomy. Pure navigation
// skeleton: each item links to its (placeholder) section page, and the bonus
// print entry links to the existing export route. No forms yet.
export default async function OccupationalIndexPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Occupational"),
  ]);
  if (!patient) notFound();

  const PrintIcon = OCCUPATIONAL_PRINT_ITEM.Icon;

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Title")}
      />
      <p className="mb-6 text-sm text-muted-foreground">{t("Subtitle")}</p>

      <div className="space-y-6">
        {OCCUPATIONAL_SECTIONS.map((group) => (
          <section key={group.slug}>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <group.Icon className="size-4 text-primary" />
              {t(group.key)}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {group.items.map(({ slug, key, Icon }) => (
                <Link
                  key={slug}
                  href={`/patients/${id}/prontuario/${slug}`}
                  className="group flex items-center gap-4 rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
                >
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1 font-semibold">{t(key)}</div>
                  <ChevronRight className="size-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5" />
                </Link>
              ))}
            </div>
          </section>
        ))}

        {/* Bonus entry — straight to the existing export route, no section page. */}
        <Link
          href={`/patients/${id}/export`}
          className="group flex items-center gap-4 rounded-2xl border bg-card p-4 transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
        >
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <PrintIcon className="size-5" />
          </div>
          <div className="min-w-0 flex-1 font-semibold">{t(OCCUPATIONAL_PRINT_ITEM.key)}</div>
          <ChevronRight className="size-5 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </AppLayout>
  );
}
