"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Brush,
} from "recharts";

type Point = { date: string; value: number };

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString(undefined, { year: "2-digit", month: "short", day: "numeric" });
}

function fullDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

/**
 * Interactive history chart for one measurement series: crosshair tooltip with
 * the full date + value, and a drag-to-zoom brush under the axis once there are
 * enough points. Renders nothing with fewer than two readings.
 */
export function MeasurementChart({
  data,
  unit,
  color = "#0ea5e9",
}: {
  data: Point[];
  unit?: string;
  color?: string;
}) {
  if (data.length < 2) return null;

  const rows = [...data]
    .sort((a, b) => String(a.date).localeCompare(String(b.date)))
    .map((p) => ({ iso: p.date, label: shortDate(p.date), value: p.value }));

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" className="text-border" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={16} />
          <YAxis
            tick={{ fontSize: 11 }}
            width={44}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `${v}`}
          />
          <Tooltip
            cursor={{ stroke: color, strokeDasharray: "4 4" }}
            content={({ active, payload }: any) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload;
              return (
                <div className="rounded-lg border bg-card px-3 py-2 text-xs shadow-md">
                  <div className="text-muted-foreground">{fullDate(p.iso)}</div>
                  <div className="font-medium">
                    {p.value}
                    {unit ? ` ${unit}` : ""}
                  </div>
                </div>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={{ r: 3, strokeWidth: 0, fill: color }}
            activeDot={{ r: 5 }}
            isAnimationActive={false}
          />
          {rows.length > 8 && (
            <Brush dataKey="label" height={24} travellerWidth={8} stroke={color} fill="transparent" />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}