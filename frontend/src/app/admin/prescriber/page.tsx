import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getPrescriber, getAdminUsers, getMemedReferenceData, getMemedCredits } from "@/lib/api";
import { PrescriberForm } from "./PrescriberForm";
import { getTranslations } from "next-intl/server";

export const dynamic = "force-dynamic";

export default async function AdminPrescriberPage() {
  const session = await auth();
  const t = await getTranslations("Admin");

  let prescriber: any = null;
  let isNew = false;

  try {
    prescriber = await getPrescriber();
  } catch {
    // 404 means no prescriber configured yet — show create form
    isNew = true;
  }

  // Fetch reference data on the server side — client components cannot
  // call server actions during initial render (api.ts is "use server").
  const [users, cities, specialties] = await Promise.all([
    getAdminUsers().catch(() => []),
    getMemedReferenceData("cities").catch(() => []),
    getMemedReferenceData("specialties").catch(() => []),
  ]);

  // Fetch signed-prescription credits — non-critical, errors are swallowed
  const credits = await getMemedCredits().catch(() => null);

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("PrescriberTitle")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isNew
            ? t("PrescriberNewSubtitle")
            : t("PrescriberEditSubtitle")}
        </p>
      </div>

      <div className="rounded-xl border bg-card p-6 space-y-4">
        <PrescriberForm
          initial={prescriber}
          isNew={isNew}
          users={users}
          cities={cities}
          specialties={specialties}
        />
      </div>

      {credits && (
        <div className="rounded-xl border bg-card p-6 space-y-3">
          <h2 className="font-medium text-sm">{t("MemedSignedPrescriptions")}</h2>
          <p className="text-3xl font-semibold tracking-tight">{credits.signed_count}</p>
          <p className="text-sm text-muted-foreground">{credits.note}</p>
        </div>
      )}
    </AppLayout>
  );
}