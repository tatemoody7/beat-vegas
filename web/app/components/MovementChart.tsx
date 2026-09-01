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
import { bookLabel } from "@/lib/books";

// One color-coded line per book. Books are sampled at different times, so
// connectNulls bridges the per-book gaps (mirrors Streamlit's line chart).
const COLORS = [
  "#38bdf8",
  "#f59e0b",
  "#34d399",
  "#f472b6",
  "#a78bfa",
  "#fb7185",
];

export default function MovementChart({
  points,
  books,
}: {
  points: MovementPoint[];
  books: string[];
}) {
  const lines = points.flatMap((p) =>
    books.map((b) => p[b]).filter((v): v is number => typeof v === "number"),
  );
  const lo = Math.min(...lines);
  const hi = Math.max(...lines);
  const pad = 0.5;

  return (
    <div className="h-72 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
        >
          <CartesianGrid stroke="#1b2336" vertical={false} />
          <XAxis
            dataKey="t"
            tick={{ fill: "#97a3bd", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243049" }}
          />
          <YAxis
            domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
            tick={{ fill: "#97a3bd", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243049" }}
            label={{
              value: "1st-half line",
              angle: -90,
              position: "insideLeft",
              fill: "#97a3bd",
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              background: "#0a0f1e",
              border: "1px solid #243049",
              borderRadius: 8,
              color: "#eef2f9",
              fontSize: 12,
            }}
          />
          {books.map((b, i) => (
            <Line
              key={b}
              type="monotone"
              dataKey={b}
              name={bookLabel(b)}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={{ r: 2 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-3 px-1 text-xs text-[var(--text-muted)]">
        {books.map((b, i) => (
          <span key={b} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            {bookLabel(b)}
          </span>
        ))}
      </div>
    </div>
  );
}
