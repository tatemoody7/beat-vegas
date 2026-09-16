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

// VARIANT 1 — emphasis. Hard Rock is the only book you can bet from Florida,
// so it is the only line that gets a colour; every other book is the same
// recessive grey and reads as "the rest of the market". Nothing here can be
// mistaken for the grade language, and it does not care how many books post.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#1b2336"; // --grid
const AXIS_RULE = "#243049"; // --axis-rule
const SURFACE = "#0a0f1e"; // --bg-2
const INK = "#eef2f9"; // --text
const HR = "#38bdf8"; // --accent — 8.91:1 on --bg-2
const REST = "#55688f"; // --border-strong — 3.42:1, ΔE 25.2 from the cyan

const HARD_ROCK = "hardrockbet";

export default function MovementChartV1({
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

  // Hard Rock draws last so it sits on top of the grey pack.
  const others = books.filter((b) => b !== HARD_ROCK);
  const hr = books.find((b) => b === HARD_ROCK);

  // The chart is decoration over a text fact: BookTable above it carries every
  // book's open and current number. This names the shape.
  const summary =
    `First-half line over time, ${books.length} book${books.length === 1 ? "" : "s"}, ` +
    `${points.length} capture times, from ${lo} to ${hi}. ` +
    `Every book's open and current number is in the table above.`;

  return (
    <div
      role="img"
      aria-label={summary}
      className="flex h-80 w-full flex-col rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3"
    >
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={points}
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
            {others.map((b) => (
              <Line
                key={b}
                type="monotone"
                dataKey={b}
                name={bookLabel(b)}
                stroke={REST}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
            {hr && (
              <Line
                key={hr}
                type="monotone"
                dataKey={hr}
                name={bookLabel(hr)}
                stroke={HR}
                strokeWidth={2.5}
                dot={{ r: 3 }}
                connectNulls
                isAnimationActive={false}
              />
            )}
          </LineChart>
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
            style={{ background: REST }}
          />
          {`${others.length} other book${others.length === 1 ? "" : "s"} — in the table above`}
        </span>
      </div>
    </div>
  );
}
