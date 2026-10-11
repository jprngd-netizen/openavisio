import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient, getNursingCare, getPregnancies } from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { NursingCareView } from "./NursingCareView";

// "Enfermagem" — the nursing-care records (OB-5). Dated and frozen notes, in the
// general or obstetric context; an obstetric record may cite the gestation it
// annotates. The record is a snapshot of its date: it shows the care at the
// instant it happened, never re-derived for "today".
export default async function NursingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Nursing"),
  ]);
  if (!patient) notFound();

  const [records, pregnancies] = await Promise.all([
    getNursingCare(id).catch(() => [] as any[]),
    getPregnancies(id).catch(() => [] as any[]),
  ]);

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Title")}
      />
      <h2 className="mb-6 text-lg font-semibold">{t("Title")}</h2>
      <NursingCareView patientId={id} records={records} pregnancies={pregnancies} />
    </AppLayout>
  );
}
