"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BankrollPoint } from "@/lib/homeBoard";

// Chart chrome from the design tokens' literal values: Recharts takes colour
// strings, not CSS variables. Keep the token name beside each one.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#1b2336"; // --grid
const AXIS_RULE = "#243049"; // --axis-rule
const START_RULE = "#55688f"; // --border-strong
const SURFACE = "#0a0f1e"; // --bg-2
const INK = "#eef2f9"; // --text
const MONEY = "#38bdf8"; // --accent — the brand cyan. Deliberately NOT green:
// green and red are the outcome language, and the bankroll is not an outcome.

// Where the real money actually went, week by week: cumulative settled units
// on real first-half bets. Cyan is the brand accent (green/red stay reserved
// for under/over outcomes); the dashed line is the starting bankroll.
export default function BankrollCurve({
  points,
  startUsd,
}: {
  points: BankrollPoint[];
  startUsd: number;
}) {
  const usd = points.map((p) => p.usd);
  const lo = Math.min(startUsd, ...usd);
  const hi = Math.max(startUsd, ...usd);
  const pad = Math.max(5, (hi - lo) * 0.15);

  // The chart is decoration over a text fact, never the only carrier of one.
  // BankrollHero's caption already names the unit and the dashed line; this
  // names the shape for anyone who cannot see it.
  const end = points[points.length - 1];
  const summary =
    `Bankroll by week: $${startUsd} at the start, $${Math.round(end.usd)} after week ` +
    `${end.week}, over ${points.length - 1} graded week${points.length === 2 ? "" : "s"}. ` +
    `Low $${Math.round(Math.min(...usd))}, high $${Math.round(Math.max(...usd))}.`;

  return (
    <div
      role="img"
      aria-label={summary}
      className="h-56 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
        >
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="week"
            tick={{ fill: AXIS, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: AXIS_RULE }}
            label={{
              value: "Week",
              position: "insideBottom",
              offset: -4,
              fill: AXIS,
              fontSize: 11,
            }}
          />
          <YAxis
            domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
            tick={{ fill: AXIS, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: AXIS_RULE }}
            tickFormatter={(v: number) => `$${v}`}
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
          <ReferenceLine
            y={startUsd}
            stroke={START_RULE}
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <Line
            type="monotone"
            dataKey="usd"
            stroke={MONEY}
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
