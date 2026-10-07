import { AppLayout } from "@/components/layout/AppLayout";
import { getEncounters, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AiNotice } from "@/components/AiNotice";
import { EncountersView } from "./EncountersView";

export default async function EncountersPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Enc");
  let patient: any = null;
  let encounters: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { encounters = await getEncounters(id); } catch { fetchError = true; }

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
      />

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : (
        <EncountersView patientId={id} encounters={encounters} />
      )}
      <AiNotice />

    </AppLayout>
  );
}