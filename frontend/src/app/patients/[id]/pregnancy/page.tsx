import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient, getPregnancies, getObstetricSummary } from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { PregnancyView } from "./PregnancyView";

// "Gestação" — the obstetric episode resource (OB-1). Lists the patient's
// pregnancies with the derived gestational age (for an explicit reference
// date) and due date, plus the GOP derived from those episodes. The record is a
// snapshot of its date: an ended episode freezes its age at `ended_at`.
export default async function PregnancyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Pregnancy"),
  ]);
  if (!patient) notFound();

  // The live panel's reference date — caller-controlled, never hidden.
  const today = new Date().toISOString().slice(0, 10);
  const [pregnancies, summary] = await Promise.all([
    getPregnancies(id, today).catch(() => [] as any[]),
    getObstetricSummary(id).catch(() => ({ gravida: 0, para: 0, aborto: 0 })),
  ]);

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Title")}
      />
      <h2 className="mb-6 text-lg font-semibold">{t("Title")}</h2>
      <PregnancyView patientId={id} episodes={pregnancies} summary={summary} initialAsOf={today} />
    </AppLayout>
  );
}
