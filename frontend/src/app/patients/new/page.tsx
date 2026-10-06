import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { PatientForm } from "../PatientForm";

export default async function NewPatientPage() {
  const role = ((await auth())?.user as any)?.role;
  if (role !== "admin" && role !== "manager") redirect("/patients");

  const [t, nav] = await Promise.all([getTranslations("PatientForm"), getTranslations("Nav")]);
  return (
    <AppLayout>
      <div className="flex items-center gap-2">
        <Link href="/patients" className="text-sm text-muted-foreground hover:text-foreground">
          {nav("Patients")}
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-2xl font-semibold tracking-tight">{t("NewTitle")}</h1>
      </div>

      <div className="max-w-2xl rounded-xl border bg-card p-6">
        <PatientForm />
      </div>
    </AppLayout>
  );
}
