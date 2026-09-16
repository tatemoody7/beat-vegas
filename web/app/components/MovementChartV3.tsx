"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MovementPoint } from "@/lib/movement";

// VARIANT 3 — Hard Rock against the market. The page is really asking one
// question: is the book you can bet moving with everyone else, or away from
// them? So the rest of the market becomes a shaded low–high band with its
// median through the middle, and Hard Rock is the one line on top of it.
// Per-book numbers stay in the table above; nothing is lost, it moves.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#1b2336"; // --grid
const AXIS_RULE = "#243049"; // --axis-rule
const SURFACE = "#0a0f1e"; // --bg-2
const INK = "#eef2f9"; // --text
const HR = "#38bdf8"; // --accent
const BAND = "#55688f"; // --border-strong
const BAND_MID = "#8b98b0"; // --push — the median, a step brighter than its band

const HARD_ROCK = "hardrockbet";

const mid = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  const h = s.length / 2;
  return s.length % 2 ? s[Math.floor(h)] : (s[h - 1] + s[h]) / 2;
};

export default function MovementChartV3({
  points,
  books,
}: {
  points: MovementPoint[];
  books: string[];
}) {
  const others = books.filter((b) => b !== HARD_ROCK);

  // Books are sampled at different times, so a raw per-timestamp min/max walks
  // a different SUBSET of books at every step and the band comes out as noise —
  // a spike is one book reporting, not the market moving. Carry each book's
  // last known number forward instead, so every step compares the same set.
  const last = new Map<string, number>();
  const data = points.map((p) => {
    for (const b of others) {
      const v = p[b];
      if (typeof v === "number") last.set(b, v);
    }
    const vals = [...last.values()];
    const hrV = p[HARD_ROCK];
    if (typeof hrV === "number") last.set(HARD_ROCK, hrV);
    return {
      t: p.t,
      band: vals.length
        ? ([Math.min(...vals), Math.max(...vals)] as [number, number])
        : undefined,
      market: vals.length ? mid(vals) : undefined,
      hr: last.has(HARD_ROCK) ? last.get(HARD_ROCK) : undefined,
    };
  });

  const all = data.flatMap((d) => [
    ...(d.band ?? []),
    ...(d.hr === undefined ? [] : [d.hr]),
  ]);
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const pad = 0.5;

  // The chart is decoration over a text fact: BookTable above it carries every
  // book's open and current number. This names the shape.
  const summary =
    `First-half line over time. Hard Rock against the ${others.length} other ` +
    `book${others.length === 1 ? "" : "s"}, ${points.length} capture times, from ${lo} to ${hi}. ` +
    `Every book's open and current number is in the table above.`;

  return (
    <div
      role="img"
      aria-label={summary}
      className="flex h-80 w-full flex-col rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3"
    >
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
          >
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: AXIS_RULE }}
            />
            <YAxis
              domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: AXIS_RULE }}
              label={{
                value: "1st-half line",
                angle: -90,
                position: "insideLeft",
                fill: AXIS,
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={{
                background: SURFACE,
                border: `1px solid ${AXIS_RULE}`,
                borderRadius: 8,
                color: INK,
                fontSize: 12,
              }}
            />
            <Area
              dataKey="band"
              name="Other books, low to high"
              stroke="none"
              fill={BAND}
              fillOpacity={0.32}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="market"
              name="Market middle"
              stroke={BAND_MID}
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="hr"
              name="Hard Rock"
              stroke={HR}
              strokeWidth={2.5}
              dot={{ r: 3 }}
              connectNulls
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 px-1 text-xs text-[var(--text-muted)]">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ background: HR }}
          />
          Hard Rock — the one you can bet
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ background: BAND_MID }}
          />
          Market middle
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-3 rounded-sm"
            style={{ background: BAND, opacity: 0.35 }}
          />
          {`Where the other ${others.length} books sit`}
        </span>
      </div>
    </div>
  );
}
