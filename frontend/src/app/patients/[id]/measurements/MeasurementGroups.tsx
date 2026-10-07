"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Trash2 } from "lucide-react";
import { deleteObservation } from "@/lib/api";
import { MeasurementChart } from "@/components/MeasurementChart";
import { measurementType } from "@/lib/measurementTypes";
import { useTranslations } from "next-intl";

type Obs = {
  id: string;
  code: string | null;
  code_display: string | null;
  value_quantity: number | null;
  value_unit: string | null;
  value_string: string | null;
  effective_date_time: string | null;
  document_reference_id: string | null;
  encounter_id: string | null;
};

export function MeasurementGroups({ observations }: { observations: Obs[] }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const t = useTranslations("Measurement");
  const tc = useTranslations("Common");

  const groups = new Map<string, { display: string; unit: string; items: Obs[] }>();
  for (const obs of observations) {
    const key = obs.code || obs.code_display || "unknown";
    if (!groups.has(key)) {
      groups.set(key, { display: obs.code_display || key, unit: obs.value_unit || "", items: [] });
    }
    groups.get(key)!.items.push(obs);
  }

  function handleDelete(id: string) {
    if (!confirm(t("DeleteConfirm"))) return;
    startTransition(async () => {
      await deleteObservation(id);
      router.refresh();
    });
  }

  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([key, group]) => {
        const chartData = group.items
          .filter((o) => o.value_quantity != null && o.effective_date_time)
          .map((o) => ({ date: o.effective_date_time!, value: o.value_quantity! }));
        const sorted = [...group.items].sort((a, b) =>
          (b.effective_date_time || "").localeCompare(a.effective_date_time || "")
        );

        return (
          <div key={key} className="rounded-xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/50 flex items-center justify-between">
              <span className="font-medium text-sm">{group.display}</span>
              {group.unit && (
                <span className="text-xs text-muted-foreground font-mono">{group.unit}</span>
              )}
            </div>

            {chartData.length >= 2 && (
              <div className="px-4 pt-4 pb-2">
                <MeasurementChart
                  data={chartData}
                  unit={group.unit || undefined}
                  color={measurementType(key)?.color ?? "#0ea5e9"}
                />
              </div>
            )}

            <table className="w-full text-sm">
              <thead className="border-b bg-muted/20">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-xs">{tc("Date")}</th>
                  <th className="px-4 py-2 text-left font-medium text-xs">{tc("Value")}</th>
                  <th className="px-4 py-2 text-left font-medium text-xs">{tc("Source")}</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {sorted.map((obs) => (
                  <tr key={obs.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-2 text-muted-foreground">
                      {obs.effective_date_time
                        ? new Date(obs.effective_date_time).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-2 font-medium">
                      {obs.value_quantity != null
                        ? `${obs.value_quantity}${group.unit ? ` ${group.unit}` : ""}`
                        : obs.value_string || "—"}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground text-xs">
                      {obs.encounter_id ? t("FromEncounter") : obs.document_reference_id ? tc("Extracted") : tc("Manual")}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleDelete(obs.id)}
                        disabled={pending}
                        className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}
