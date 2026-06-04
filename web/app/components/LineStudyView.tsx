"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LineBucket } from "@/lib/lineStudy";

// Interactive chart + highlight + table. Mirrors the Streamlit Line Study tab:
// bars color-coded green/red vs the 52.4% breakeven, dashed breakeven line,
// a highlighted line metric, and the full ranked table.
export default function LineStudyView({
  buckets,
  breakeven,
}: {
  buckets: LineBucket[];
  breakeven: number;
}) {
  const [highlight, setHighlight] = useState(24.5);

  // Chart wants ascending line order; table stays ranked by under_pct (as given).
  const chartData = [...buckets].sort((a, b) => a.line - b.line);
  const maxPct = buckets.reduce((m, b) => Math.max(m, b.under_pct), 0);
  const yMax = Math.max(70, Math.ceil(maxPct + 5));

  const hl = buckets.find((b) => b.line === highlight);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
        Highlight line
        <input
          type="number"
          step={0.5}
          value={highlight}
          onChange={(e) => setHighlight(Number(e.target.value))}
          className="bv-input w-24 font-mono"
        />
        {hl ? (
          <span className="text-[var(--text-muted)]">
            Under {highlight}:{" "}
            <b
              style={{
                color: hl.under_pct >= breakeven ? "#16a34a" : "#dc2626",
              }}
            >
              {hl.under_pct}%
            </b>{" "}
            ({hl.under}/{hl.games} ·{" "}
            {hl.under_pct >= breakeven ? "beats" : "below"} breakeven)
          </span>
        ) : (
          <span className="text-[var(--text-dim)]">
            no bucket at {highlight}
          </span>
        )}
      </div>

      <div className="h-72 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
          >
            <XAxis
              dataKey="line"
              tick={{ fill: "#97a3bd", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#243049" }}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: "#97a3bd", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#243049" }}
              label={{
                value: "Under %",
                angle: -90,
                position: "insideLeft",
                fill: "#97a3bd",
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: "#243049", opacity: 0.4 }}
              contentStyle={{
                background: "#0a0f1e",
                border: "1px solid #243049",
                borderRadius: 8,
                color: "#eef2f9",
                fontSize: 12,
              }}
              formatter={(value, _name, item) => {
                const b = item?.payload as LineBucket;
                return [`${value}%  (${b.under}/${b.games})`, `Line ${b.line}`];
              }}
            />
            <ReferenceLine
              y={breakeven}
              stroke="#97a3bd"
              strokeDasharray="4 4"
              label={{
                value: `${breakeven}% break-even`,
                fill: "#97a3bd",
                fontSize: 10,
                position: "right",
              }}
            />
            <Bar dataKey="under_pct" radius={[2, 2, 0, 0]}>
              {chartData.map((b) => (
                <Cell
                  key={b.line}
                  fill={b.under_pct >= breakeven ? "#16a34a" : "#dc2626"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bv-table-wrap">
        <table className="bv-table">
          <thead>
            <tr>
              <th>Line</th>
              <th>Games</th>
              <th>Under</th>
              <th>Push</th>
              <th>Under %</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((b) => (
              <tr
                key={b.line}
                className={
                  b.line === highlight ? "bg-[var(--accent-soft)]" : ""
                }
              >
                <td className="font-mono text-[var(--text)]">{b.line}</td>
                <td className="text-[var(--text-muted)]">{b.games}</td>
                <td className="text-[var(--text-muted)]">{b.under}</td>
                <td className="text-[var(--text-muted)]">{b.push}</td>
                <td
                  className="font-mono font-semibold"
                  style={{
                    color: b.under_pct >= breakeven ? "#16a34a" : "#dc2626",
                  }}
                >
                  {b.under_pct}%
                </td>
                <td className="text-[var(--text-dim)]">{b.line_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
