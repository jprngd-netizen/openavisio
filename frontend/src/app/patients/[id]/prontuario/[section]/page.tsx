import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient, getOrganization } from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { Info } from "lucide-react";
import { OCCUPATIONAL_ITEM_BY_SLUG } from "@/lib/occupationalSections";
import { CoverView } from "./CoverView";

// Per-section page. Resolves the section slug from the taxonomy; an unknown
// slug is a 404. Section #1 ("cover") renders the real "Capa do Prontuário";
// the remaining sections still show the styled "content coming" placeholder.
export default async function OccupationalSectionPage({
  params,
}: {
  params: Promise<{ id: string; section: string }>;
}) {
  const { id, section } = await params;
  const resolved = OCCUPATIONAL_ITEM_BY_SLUG[section];
  if (!resolved) notFound();

  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Occupational"),
  ]);
  if (!patient) notFound();

  const { group, item } = resolved;

  // Section #1 — the occupational record cover. Identity and the record header
  // read from the patient/organization; only the employment block is editable.
  const isCover = section === "cover";
  const organization = isCover ? await getOrganization().catch(() => null) : null;
  const recordNumber = String(patient.id).replace(/-/g, "").slice(0, 8).toUpperCase();

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[
          { label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` },
          { label: t("Title"), href: `/patients/${id}/prontuario` },
        ]}
        current={t(item.key)}
      />

      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <group.Icon className="size-4 text-primary" />
        <span>{t(group.key)}</span>
      </div>

      <h2 className="mb-4 text-lg font-semibold">{t(item.key)}</h2>

      {isCover ? (
        <CoverView
          patientId={id}
          patient={patient}
          organizationName={organization?.name ?? null}
          recordNumber={recordNumber}
        />
      ) : (
        <div className="rounded-xl border bg-card p-6">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 size-5 shrink-0 text-primary" />
            <p className="text-sm text-muted-foreground">{t("Placeholder")}</p>
          </div>
        </div>
      )}
    </AppLayout>
  );
}
