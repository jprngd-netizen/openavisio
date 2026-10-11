import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient, listNewbornRecords } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { NewbornView, type OutcomeOption } from "./NewbornView";

// "Recém-nascido" — the structured newborn record (FExEO-SUS I.2/I.3, R4). A
// NewbornRecord is 1:1 with a PregnancyOutcome, so this section lists the
// patient's closed live-birth outcomes and, for each, its record (if any). The
// record is a snapshot of the birth date; nothing is re-derived for "today".
export default async function NewbornPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Newborn"),
  ]);
  if (!patient) notFound();

  const entries = await listNewbornRecords(id).catch(() => [] as any[]);

  const outcomes: OutcomeOption[] = entries.map((e: any) => {
    const p = e.pregnancy ?? {};
    const outcome = p.outcome ?? {};
    return {
      pregnancyId: p.id,
      pregnancyLabel: p.lmp_date ? formatDate(p.lmp_date) : String(p.id ?? "").slice(0, 8),
      outcomeType: outcome.outcome_type ?? "",
      outcomeDate: outcome.outcome_date ? formatDate(outcome.outcome_date) : "",
      record: e.record ?? null,
    };
  });

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Title")}
      />
      <h2 className="mb-6 text-lg font-semibold">{t("Title")}</h2>
      <NewbornView patientId={id} outcomes={outcomes} />
    </AppLayout>
  );
}
