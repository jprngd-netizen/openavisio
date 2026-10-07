import { AppLayout } from "@/components/layout/AppLayout";
import { LogsClient } from "./LogsClient";
import { getTranslations } from "next-intl/server";

export default async function AdminLogsPage() {
  const t = await getTranslations("Admin");
  return (
    <AppLayout>
      <h1 className="text-xl font-bold">{t("LogsTitle")}</h1>
      <LogsClient />
    </AppLayout>
  );
}
