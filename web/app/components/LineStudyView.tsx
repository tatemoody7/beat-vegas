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
import { labelOf, LINE_SOURCE_TEXT } from "@/lib/labels";
import type { LineBucket } from "@/lib/lineStudy";

// Interactive chart + highlight + table: bars coloured green/red against the
// break-even rate, a dashed break-even line, one total picked out, and the
// full ranked table. "Line from" says whether the total is a book's open or
// our estimate — never the raw enum (spec §24.18).

// Chart chrome comes from the design tokens' literal values: Recharts takes
// colour strings, not CSS variables.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#3a4a6b"; // --border
const GOOD = "#3ddc84"; // --good
const BAD = "#f87171"; // --bad
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
        Show one total
        <input
          type="number"
          step={0.5}
          value={highlight}
          onChange={(e) => setHighlight(Number(e.target.value))}
          className="bv-input w-24 font-mono"
        />
        {hl ? (
          <span className="text-[var(--text-muted)]">
            {`Under ${highlight}: `}
            <b style={{ color: hl.under_pct >= breakeven ? GOOD : BAD }}>
              {`${hl.under_pct}%`}
            </b>
            {` (${hl.under} of ${hl.games} · ${
              hl.under_pct >= breakeven
                ? "beats break-even"
                : "below break-even"
            })`}
          </span>
        ) : (
          <span className="text-[var(--text-dim)]">
            {`no games at ${highlight}`}
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
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              label={{
                value: "Under %",
                angle: -90,
                position: "insideLeft",
                fill: AXIS,
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: GRID, opacity: 0.4 }}
              contentStyle={{
                background: "#0a0f1e",
                border: `1px solid ${GRID}`,
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
              stroke={AXIS}
              strokeDasharray="4 4"
              label={{
                value: `${breakeven}% break-even`,
                fill: AXIS,
                fontSize: 10,
                position: "right",
              }}
            />
            <Bar dataKey="under_pct" radius={[2, 2, 0, 0]}>
              {chartData.map((b) => (
                <Cell
                  key={b.line}
                  fill={b.under_pct >= breakeven ? GOOD : BAD}
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
              <th className="bv-num">Total</th>
              <th className="bv-num">Games</th>
              <th className="bv-num">Under</th>
              <th className="bv-num">Push</th>
              <th className="bv-num">Under %</th>
              <th>Line from</th>
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
                <td className="bv-num font-mono text-[var(--text)]">
                  {b.line}
                </td>
                <td className="bv-num text-[var(--text-muted)]">{b.games}</td>
                <td className="bv-num text-[var(--text-muted)]">{b.under}</td>
                <td className="bv-num text-[var(--text-muted)]">{b.push}</td>
                <td
                  className="bv-num font-mono font-semibold"
                  style={{ color: b.under_pct >= breakeven ? GOOD : BAD }}
                >
                  {`${b.under_pct}%`}
                </td>
                <td className="text-[var(--text-dim)]">
                  {labelOf(LINE_SOURCE_TEXT, b.line_source, "our estimate")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-[var(--text-dim)]">
        {`Bars above the dashed line beat the ${breakeven}% you need at -110.`}
      </p>
    </div>
  );
}
