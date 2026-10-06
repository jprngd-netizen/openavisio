import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getPatient } from "@/lib/api";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { PatientForm } from "../../PatientForm";

// Demographics edit — the CPF/address had no way in after creation, since the
// only form lived on /patients/new.
export default async function EditPatientPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const role = ((await auth())?.user as any)?.role;
  if (role !== "admin" && role !== "manager") redirect(`/patients/${id}`);

  const [patient, t] = await Promise.all([
    getPatient(id).catch(() => null),
    getTranslations("PatientForm"),
  ]);
  if (!patient) notFound();

  return (
    <AppLayout>
      <div className="flex items-center gap-2">
        <Link href={`/patients/${id}`} className="text-sm text-muted-foreground hover:text-foreground">
          {patient.given_name} {patient.family_name}
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-2xl font-semibold tracking-tight">{t("EditTitle")}</h1>
      </div>

      <div className="max-w-2xl rounded-xl border bg-card p-6">
        <PatientForm patientId={id} initial={patient as any} />
      </div>
    </AppLayout>
  );
}