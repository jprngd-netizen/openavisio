import { auth } from "@/auth";
import { AppLayout } from "@/components/layout/AppLayout";
import { getPrescriptions, getPatient, getPrescription } from "@/lib/api";
import { getTranslations, getLocale } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle, ExternalLink } from "lucide-react";
import { PrescriptionList } from "./PrescriptionList";
import { NewPrescriptionButton } from "./NewPrescriptionButton";
import { AttachPrescriptionPanel } from "./AttachPrescriptionPanel";
import { createPrescriptionAction } from "./actions";

export default async function PrescriptionsPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ rx?: string; error?: string }>;
}) {
  const { id } = await params;
  const { rx, error } = await searchParams;
  const t = await getTranslations("Prescriptions");
  const locale = await getLocale();
  let patient: any = null;
  let prescriptions: any[] = [];
  let fetchError = false;
  let isPrescriber = false;

  try { patient = await getPatient(id); } catch {}
  try { prescriptions = await getPrescriptions(id); } catch { fetchError = true; }

  if (rx) {
    try {
      const rxData = await getPrescription(rx);
      const session = await auth();
      const userId = (session as any)?.id;
      if (userId && rxData.prescriber?.user_id === userId) {
        isPrescriber = true;
      }
    } catch {
      // Non-fatal — the editor will show its own error
    }
  }

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

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {error === "no_prescriber" ? t("NeedPrescriber") : t("CreateError")}
        </div>
      )}

      {rx ? (
        <PrescriptionList prescriptions={prescriptions} rxPrescriptionId={rx} isPrescriber={isPrescriber} />
      ) : (
        <>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
            <a
              href="https://memed.com.br/login"
              target="_blank"
              rel="noopener noreferrer"
              data-testid="prescribe-on-memed"
              className="inline-flex items-center gap-2 rounded-lg border border-primary text-primary px-3 py-2 text-sm font-medium hover:bg-primary/5 transition-colors"
            >
              <ExternalLink className="size-4" />
              {t("MemedPrescribe")}
            </a>
            <form action={createPrescriptionAction}>
              <input type="hidden" name="patientId" value={id} />
              <NewPrescriptionButton />
            </form>
          </div>
          <p className="mb-4 text-xs text-muted-foreground">{t("MemedPrescribeHint")}</p>

          <AttachPrescriptionPanel patientId={id} />

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
        </>
      )}
    </AppLayout>
  );
}
