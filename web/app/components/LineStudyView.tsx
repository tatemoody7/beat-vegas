"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
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
const GRID = "#1b2336"; // --grid
const AXIS_RULE = "#243049"; // --axis-rule
const HOVER = "#3a4a6b"; // --border — the hover cursor wash, not a chart rule
const SURFACE = "#0a0f1e"; // --bg-2
const INK = "#eef2f9"; // --text
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

  // Chart wants ascending line order; table stays ranked by under_pct (as
  // given). Colour rides on the datum as `fill`, which <Bar> picks up per
  // rectangle — one fewer child component than a <Cell> per bar.
  const chartData = [...buckets]
    .sort((a, b) => a.line - b.line)
    .map((b) => ({ ...b, fill: b.under_pct >= breakeven ? GOOD : BAD }));
  const maxPct = buckets.reduce((m, b) => Math.max(m, b.under_pct), 0);
  const yMax = Math.max(70, Math.ceil(maxPct + 5));

  const hl = buckets.find((b) => b.line === highlight);
  // The chart is not the only carrier: the ranked table below says every number.
  const beats = buckets.filter((b) => b.under_pct >= breakeven).length;

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

      <div
        role="img"
        aria-label={`Under rate by first-half total, ${buckets.length} totals with enough games. ${beats} of them beat the ${breakeven}% break-even rate. The full numbers are in the table below.`}
        className="h-72 w-full rounded-xl border border-[var(--border-soft)] bg-[var(--bg-2)] p-3"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
          >
            <XAxis
              dataKey="line"
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: AXIS_RULE }}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: AXIS, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: AXIS_RULE }}
              label={{
                value: "Under %",
                angle: -90,
                position: "insideLeft",
                fill: AXIS,
                fontSize: 11,
              }}
            />
            <Tooltip
              cursor={{ fill: HOVER, opacity: 0.4 }}
              contentStyle={{
                background: SURFACE,
                border: `1px solid ${AXIS_RULE}`,
                borderRadius: 8,
                color: INK,
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
              // "right" parks the label outside the plot, where the container
              // clips it to a single character. Inside-top-left always fits.
              label={{
                value: `${breakeven}% break-even`,
                fill: AXIS,
                fontSize: 10,
                position: "insideTopLeft",
              }}
            />
            {/* isAnimationActive={false} is load-bearing, not a preference.
                Under Recharts 3.8 the bars animate up from height 0 and the
                animation never completes here, so every rectangle stays at 0
                and Recharts renders an EMPTY recharts-inactive-bar group —
                a blank plot area beside a full table. It went unnoticed
                because the only page that mounted this chart scoped it to
                the current season, which never has a total with enough
                graded games to draw. */}
            <Bar
              dataKey="under_pct"
              isAnimationActive={false}
              radius={[2, 2, 0, 0]}
            />
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
