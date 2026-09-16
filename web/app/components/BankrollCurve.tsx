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

  return (
    <div className="h-56 w-full rounded-xl border border-[var(--border)] bg-[var(--bg-2)] p-3">
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
            tickFormatter={(v: number) => `$${v}`}
          />
          <Tooltip
            contentStyle={{
              background: "var(--bg-2)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              color: "var(--text)",
              fontSize: 12,
            }}
          />
          <ReferenceLine
            y={startUsd}
            stroke={AXIS}
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <Line
            type="monotone"
            dataKey="usd"
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
