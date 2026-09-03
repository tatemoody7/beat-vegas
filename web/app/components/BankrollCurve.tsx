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
    <div className="h-56 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={points}
          margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
        >
          <CartesianGrid stroke="#1b2336" vertical={false} />
          <XAxis
            dataKey="week"
            tick={{ fill: "#97a3bd", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243049" }}
            label={{
              value: "Week",
              position: "insideBottom",
              offset: -4,
              fill: "#97a3bd",
              fontSize: 11,
            }}
          />
          <YAxis
            domain={[Math.floor(lo - pad), Math.ceil(hi + pad)]}
            tick={{ fill: "#97a3bd", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243049" }}
            tickFormatter={(v: number) => `$${v}`}
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
          <ReferenceLine
            y={startUsd}
            stroke="#5e6c87"
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <Line
            type="monotone"
            dataKey="usd"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={{ r: 3 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
