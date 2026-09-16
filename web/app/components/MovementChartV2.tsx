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

// VARIANT 2 — a real categorical ramp, deliberately disjoint from the grade
// language. Validated dark against --bg-2 on the adjacent pairlist: all five
// checks PASS (worst adjacent CVD ΔE 16.7, normal-vision ΔE 26.0, all ≥3:1),
// and every slot sits ≥15 ΔE from --good, --warn, --bad and --push.
//
// It FAILS `--pairs all` (blue/indigo/violet collapse to ΔE 1.8 under
// deuteranopia) and movement lines do cross, so the dash patterns below are
// not decoration — they are the secondary encoding that failure requires.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#1b2336"; // --grid
const AXIS_RULE = "#243049"; // --axis-rule
const SURFACE = "#0a0f1e"; // --bg-2
const INK = "#eef2f9"; // --text
const REST = "#55688f"; // --border-strong — the folded tail

// Fixed order. Never cycled: past slot 6 a book folds into the grey tail.
const SLOTS = [
  { c: "#7b6ee0", d: undefined }, // violet
  { c: "#199e70", d: "6 3" }, // teal
  { c: "#6366f1", d: "2 3" }, // indigo
  { c: "#b06a2c", d: "10 4" }, // tan
  { c: "#2a78d6", d: "1 4" }, // blue
  { c: "#c43f70", d: "8 3 2 3" }, // magenta
];

const HARD_ROCK = "hardrockbet";

export default function MovementChartV2({
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

  // Hard Rock always takes slot 1; the rest fill by how much they have moved,
  // so the books that are actually doing something get the named colours and
  // the quiet ones fold. Colour follows the book, never its row number on a
  // filtered view — the order here is stable for a given game.
  const ranked = books
    .filter((b) => b !== HARD_ROCK)
    .map((b) => {
      const vals = points
        .map((p) => p[b])
        .filter((v): v is number => typeof v === "number");
      return { b, span: vals.length ? Math.max(...vals) - Math.min(...vals) : 0 };
    })
    .sort((x, y) => y.span - x.span || x.b.localeCompare(y.b))
    .map((x) => x.b);
  const named = [
    ...(books.includes(HARD_ROCK) ? [HARD_ROCK] : []),
    ...ranked,
  ].slice(0, SLOTS.length);
  const tail = books.filter((b) => !named.includes(b));

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
            {tail.map((b) => (
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
            {named.map((b, i) => (
              <Line
                key={b}
                type="monotone"
                dataKey={b}
                name={bookLabel(b)}
                stroke={SLOTS[i].c}
                strokeDasharray={SLOTS[i].d}
                strokeWidth={2}
                dot={{ r: 2 }}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 px-1 text-xs text-[var(--text-muted)]">
        {named.map((b, i) => (
          <span key={b} className="flex items-center gap-1.5">
            <svg width="14" height="8" aria-hidden>
              <line
                x1="0"
                y1="4"
                x2="14"
                y2="4"
                stroke={SLOTS[i].c}
                strokeWidth="2"
                strokeDasharray={SLOTS[i].d}
              />
            </svg>
            {bookLabel(b)}
          </span>
        ))}
        {tail.length > 0 && (
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{ background: REST }}
            />
            {`${tail.length} more, barely moved`}
          </span>
        )}
      </div>
    </div>
  );
}
