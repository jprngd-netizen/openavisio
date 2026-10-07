import { AppLayout } from "@/components/layout/AppLayout";
import { getAdminGroups } from "@/lib/api";
import Link from "next/link";
import { formatDate } from "@/lib/utils";
import { AlertCircle } from "lucide-react";
import { CreateGroupButton } from "./CreateGroupButton";
import { getTranslations } from "next-intl/server";

export default async function AdminGroupsPage() {
  const t = await getTranslations("Admin");
  const tc = await getTranslations("Common");
  let groups: any[] = [], fetchError = false;
  try { groups = await getAdminGroups(); } catch { fetchError = true; }

  return (
    <AppLayout>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{t("Groups")}</h1>
        <CreateGroupButton />
      </div>

      {fetchError && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("GroupsLoadError")}
        </div>
      )}

      {!fetchError && groups.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("NoGroups")}</div>
      ) : !fetchError ? (
        <div className="rounded-xl border bg-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">{tc("Name")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Members")}</th>
                <th className="px-4 py-3 text-left font-medium">{t("Created")}</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {groups.map((g: any) => (
                <tr key={g.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/group/${g.id}`} className="hover:underline">{g.name}</Link>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{g.member_count ?? 0}</td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{formatDate(g.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppLayout>
  );
}
