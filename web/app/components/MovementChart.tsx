"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MovementPoint } from "@/lib/movement";

// One color-coded line per book. Books are sampled at different times, so
// connectNulls bridges the per-book gaps (mirrors Streamlit's line chart).
const COLORS = ["#60a5fa", "#f59e0b", "#34d399", "#f472b6", "#a78bfa", "#f87171"];

export default function MovementChart({
  points,
  books,
}: {
  points: MovementPoint[];
  books: string[];
}) {
  const lines = points
    .flatMap((p) => books.map((b) => p[b]).filter((v): v is number => typeof v === "number"));
  const lo = Math.min(...lines);
  const hi = Math.max(...lines);
  const pad = 0.5;

  return (
    <div className="h-72 w-full rounded-xl border border-gray-800 bg-gray-950 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#1f2937" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
          />
          <YAxis
            domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#374151" }}
            label={{
              value: "1H line",
              angle: -90,
              position: "insideLeft",
              fill: "#9ca3af",
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              background: "#0a0a0a",
              border: "1px solid #374151",
              borderRadius: 8,
              color: "#e5e7eb",
              fontSize: 12,
            }}
          />
          {books.map((b, i) => (
            <Line
              key={b}
              type="monotone"
              dataKey={b}
              name={b}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={{ r: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-3 px-1 text-xs text-gray-400">
        {books.map((b, i) => (
          <span key={b} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            {b}
          </span>
        ))}
      </div>
    </div>
  );
}
