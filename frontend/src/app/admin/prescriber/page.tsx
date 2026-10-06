import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getPrescriber, getAdminUsers, getMemedReferenceData } from "@/lib/api";
import { PrescriberForm } from "./PrescriberForm";

export const dynamic = "force-dynamic";

export default async function AdminPrescriberPage() {
  const session = await auth();

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

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Prescriber</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {isNew
            ? "Configure the healthcare professional authorized to issue prescriptions."
            : "Edit the registered prescriber details."}
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
    </AppLayout>
  );
}