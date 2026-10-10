import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import { getPatient, getOrganization, getSafetySummary } from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { CoverView } from "./CoverView";

// "Capa do Prontuário" — the clinical chart front page. Identity and the record
// header read from the patient/organization; nothing is editable here except the
// patient's own registration (via the edit link).
export default async function CoverPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t, organization, safety] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Patient"),
    getOrganization().catch(() => null),
    getSafetySummary(id).catch(() => null),
  ]);
  if (!patient) notFound();

  const recordNumber = String(patient.id).replace(/-/g, "").slice(0, 8).toUpperCase();

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Cover")}
      />
      <h2 className="mb-6 text-lg font-semibold">{t("Cover")}</h2>
      <CoverView
        patientId={id}
        patient={patient}
        organizationName={organization?.name ?? null}
        recordNumber={recordNumber}
        safety={
          safety ?? { allergies: [], medications: [], conditions: [] }
        }
      />
    </AppLayout>
  );
}
