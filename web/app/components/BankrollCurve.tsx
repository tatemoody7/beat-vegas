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

// Recharts wants literals; these are the tokens from globals.css, the same
// three every chart on the site uses (GapLadderChart, LineStudyView).
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#3a4a6b"; // --border
const ACCENT = "#38bdf8"; // --accent

const signedU = (v: number) => `${v > 0 ? "+" : ""}${v}u`;

// Where our bets actually went, week by week: cumulative settled units on real
// first-half bets. In units, not dollars, since 2026-09-28 (the public site
// shows no stake size). Cyan is the brand accent (green/red stay reserved for
// under/over outcomes); the dashed line is zero, where the season started.
export default function BankrollCurve({ points }: { points: BankrollPoint[] }) {
  const units = points.map((p) => p.units);
  const lo = Math.min(0, ...units);
  const hi = Math.max(0, ...units);
  const pad = Math.max(0.5, (hi - lo) * 0.15);

  return (
    // No frame of its own: it sits inside the ledger card, and a box in a box
    // is the "too many boxes" Tate named (2026-09-16).
    <div className="h-52 w-full">
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
            axisLine={{ stroke: GRID }}
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
            axisLine={{ stroke: GRID }}
            tickFormatter={(v: number) => signedU(v)}
          />
          <Tooltip
            formatter={(v) => [signedU(Number(v)), "units"]}
            contentStyle={{
              background: "var(--bg-2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--text)",
              fontSize: 12,
            }}
          />
          <ReferenceLine
            y={0}
            stroke={AXIS}
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <Line
            type="monotone"
            dataKey="units"
            stroke={ACCENT}
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
