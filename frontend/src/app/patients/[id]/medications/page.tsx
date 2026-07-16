import { AppLayout } from "@/components/layout/AppLayout";
import { getMedications, getPatient } from "@/lib/api";
import { getTranslations, getLocale } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { formatDate } from "@/lib/utils";
import { AlertCircle } from "lucide-react";
import { AddMedicationPanel } from "./AddMedicationPanel";
import { MedicationActions } from "./MedicationActions";
import { AiNotice } from "@/components/AiNotice";

export default async function MedicationsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Med");
  const locale = await getLocale();
  let patient: any = null;
  let medications: any[] = [];
  let fetchError = false;

  try { patient = await getPatient(id); } catch {}
  try { medications = await getMedications(id); } catch { fetchError = true; }

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AddMedicationPanel patientId={id}>
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Title")}
          className=""
        />
      </AddMedicationPanel>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : medications.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{t("NameCol")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Dosage")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Period")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Status")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Source")}</th>
                <th className="w-px px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y">
              {medications.map((m: any) => (
                <tr key={m.id} className="hover:bg-muted/30 transition-colors">
                  <td className={`px-4 py-3 font-medium ${m.is_active ? "" : "opacity-50"}`}>{m.medication_display}</td>
                  <td className={`px-4 py-3 text-muted-foreground ${m.is_active ? "" : "opacity-50"}`}>{m.dosage_text || (m.dose_quantity ? `${m.dose_quantity} ${m.dose_unit || ""}` : "—")}</td>
                  <td className={`px-4 py-3 text-muted-foreground ${m.is_active ? "" : "opacity-50"}`}>
                    {m.effective_start ? formatDate(m.effective_start, locale) : "—"}
                    {m.effective_end ? ` – ${formatDate(m.effective_end, locale)}` : (m.effective_start ? ` – ${t("Ongoing")}` : "")}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${m.is_active ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"}`}>
                      {m.is_active ? t("Active") : t("Ended")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {m.document_reference_id ? t("Extracted") : t("Manual")}
                  </td>
                  <td className="w-px whitespace-nowrap px-4 py-3">
                    <MedicationActions med={m} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <AiNotice />

    </AppLayout>
  );
}
