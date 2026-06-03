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
      <div className="flex items-center gap-2 text-sm text-gray-400">
        Highlight line
        <input
          type="number"
          step={0.5}
          value={highlight}
          onChange={(e) => setHighlight(Number(e.target.value))}
          className="w-24 rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100 focus:border-gray-500 focus:outline-none"
        />
        {hl ? (
          <span className="text-gray-300">
            Under {highlight}:{" "}
            <b style={{ color: hl.under_pct >= breakeven ? "#16a34a" : "#dc2626" }}>
              {hl.under_pct}%
            </b>{" "}
            ({hl.under}/{hl.games} ·{" "}
            {hl.under_pct >= breakeven ? "beats" : "below"} breakeven)
          </span>
        ) : (
          <span className="text-gray-600">no bucket at {highlight}</span>
        )}
      </div>

      <div className="h-72 w-full rounded-xl border border-gray-800 bg-gray-950 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <XAxis
              dataKey="line"
              tick={{ fill: "#9ca3af", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#374151" }}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: "#9ca3af", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#374151" }}
              label={{
                value: "Under %",
                angle: -90,
                position: "insideLeft",
                fill: "#9ca3af",
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: "#1f2937", opacity: 0.4 }}
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid #374151",
                borderRadius: 8,
                color: "#e5e7eb",
                fontSize: 12,
              }}
              formatter={(value, _name, item) => {
                const b = item?.payload as LineBucket;
                return [`${value}%  (${b.under}/${b.games})`, `Line ${b.line}`];
              }}
            />
            <ReferenceLine
              y={breakeven}
              stroke="#9ca3af"
              strokeDasharray="4 4"
              label={{
                value: `${breakeven}% break-even`,
                fill: "#9ca3af",
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

      <div className="overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-left text-gray-400">
            <tr>
              <th className="px-3 py-2 font-medium">Line</th>
              <th className="px-3 py-2 font-medium">Games</th>
              <th className="px-3 py-2 font-medium">Under</th>
              <th className="px-3 py-2 font-medium">Push</th>
              <th className="px-3 py-2 font-medium">Under %</th>
              <th className="px-3 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((b) => (
              <tr
                key={b.line}
                className={`border-t border-gray-800 ${
                  b.line === highlight ? "bg-gray-900/60" : ""
                }`}
              >
                <td className="px-3 py-1.5 text-gray-200">{b.line}</td>
                <td className="px-3 py-1.5 text-gray-400">{b.games}</td>
                <td className="px-3 py-1.5 text-gray-400">{b.under}</td>
                <td className="px-3 py-1.5 text-gray-400">{b.push}</td>
                <td
                  className="px-3 py-1.5 font-medium"
                  style={{ color: b.under_pct >= breakeven ? "#16a34a" : "#dc2626" }}
                >
                  {b.under_pct}%
                </td>
                <td className="px-3 py-1.5 text-gray-500">{b.line_source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
