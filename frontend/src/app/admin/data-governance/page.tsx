import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { DataGovernanceClient } from "./DataGovernanceClient";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

export default async function DataGovernancePage() {
  const session = await auth();
  const t = await getTranslations("Admin");
  const token = (session as any)?.accessToken;

  let categories: any[] = [];
  try {
    const res = await fetch(`${API}/api/admin/data-categories`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (res.ok) categories = await res.json();
  } catch {}

  return (
    <AppLayout>
      <h1 className="text-xl font-bold mb-1">{t("DataGovernance")}</h1>
      <p className="text-sm text-muted-foreground mb-4">
        {t("DataGovernanceSubtitle")}
      </p>
      <div className="max-w-3xl">
        <DataGovernanceClient categories={categories} />
      </div>
    </AppLayout>
  );
}
