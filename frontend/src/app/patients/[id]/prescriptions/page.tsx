import { AppLayout } from "@/components/layout/AppLayout";
import { getPrescriptions, getPatient } from "@/lib/api";
import { getTranslations, getLocale } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { PrescriptionList } from "./PrescriptionList";

export default async function PrescriptionsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Prescriptions");
  const locale = await getLocale();
  let patient: any = null;
  let prescriptions: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { prescriptions = await getPrescriptions(id); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <Breadcrumb
        crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
        current={t("Title")}
        className=""
      />

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : prescriptions.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <PrescriptionList prescriptions={prescriptions} />
      )}
    </AppLayout>
  );
}