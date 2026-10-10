import { AppLayout } from "@/components/layout/AppLayout";
import { Breadcrumb } from "@/components/Breadcrumb";
import {
  getPatient,
  getConditions,
  getMedications,
  getClinicalHistory,
  getAllergies,
  getImmunizations,
  getFamilyHistory,
} from "@/lib/api";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { AntecedentsView } from "./AntecedentsView";

// "Antecedentes" — the longitudinal anamnesis: personal/family/surgical history,
// allergies and habits (free text), plus the derived antecedents (diagnoses,
// medications) which are the canonical conditions/medications resources, edited
// in place — never duplicated.
export default async function AntecedentsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("Patient"),
  ]);
  if (!patient) notFound();

  const [clinicalHistory, conditions, medications, allergies, immunizations, familyHistory] = await Promise.all([
    getClinicalHistory(id).catch(() => null),
    getConditions(id).catch(() => []),
    getMedications(id).catch(() => []),
    getAllergies(id).catch(() => []),
    getImmunizations(id).catch(() => []),
    getFamilyHistory(id).catch(() => []),
  ]);

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Antecedents")}
      />
      <h2 className="mb-6 text-lg font-semibold">{t("Antecedents")}</h2>
      <AntecedentsView
        patientId={id}
        history={clinicalHistory}
        conditions={conditions}
        medications={medications}
        allergies={allergies}
        immunizations={immunizations}
        familyHistory={familyHistory}
      />
    </AppLayout>
  );
}
