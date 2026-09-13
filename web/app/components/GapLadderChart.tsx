"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BandRow } from "@/lib/postmortem";

// THE finding, as a picture: the wider the gap between Hard Rock's first-half
// line and our number, the more often the under wins. It was an 8-column table
// under a 60-word caption, while a tangent (which totals go under most) had the
// page's only chart — the page ranked its own findings upside down (Tate
// 2026-09-13). The table stays directly beneath this for the range, the
// probability and the ROI; this carries the shape.
//
// Approved on the rule "if it isn't obvious I don't want it": the bars climb
// left to right, the ones that make money are green, and the break-even line
// is drawn and labelled. Nothing here needs a paragraph to read.

// Recharts takes colour strings, not CSS variables — same literals as
// LineStudyView, from the design tokens.
const AXIS = "#aab6cc"; // --text-muted
const GRID = "#3a4a6b"; // --border
const GOOD = "#3ddc84"; // --good
const BAD = "#f87171"; // --bad

/** Rows thinner than this say nothing; they plot, but greyed. */
const THIN = "#6b7a99";

export default function GapLadderChart({
  rows,
  breakeven,
}: {
  rows: BandRow[];
  breakeven: number;
}) {
  const data = rows
    .filter((r) => r.hitPct !== null)
    .map((r) => ({
      bucket: r.bucket,
      hitPct: r.hitPct as number,
      n: r.n,
      record: r.record,
      // A band under 30 games is greyed in the table for the same reason it is
      // greyed here: it is a count, not a rate, and colouring it green would
      // promise an edge the sample cannot support.
      fill:
        r.size === "small"
          ? THIN
          : (r.hitPct as number) >= breakeven
            ? GOOD
            : BAD,
    }));
  if (data.length === 0) return null;

  const maxPct = data.reduce((m, d) => Math.max(m, d.hitPct), 0);
  const minPct = data.reduce((m, d) => Math.min(m, d.hitPct), 100);
  // Round the axis out to whole 5s and tick it by hand. Recharts' own choice
  // inside a tight domain came out 40/47/54/61/65, which reads like an
  // accident rather than a scale.
  const lo = Math.max(0, Math.floor((minPct - 4) / 5) * 5);
  const hi = Math.ceil((maxPct + 4) / 5) * 5;
  const ticks: number[] = [];
  for (let t = lo; t <= hi; t += 5) ticks.push(t);

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 12, right: 16, bottom: 28, left: 0 }}
        >
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="bucket"
            tick={{ fill: AXIS, fontSize: 11 }}
            stroke={GRID}
            label={{
              value: "How far Hard Rock’s line sat above our number (points)",
              position: "insideBottom",
              offset: -16,
              fill: AXIS,
              fontSize: 11,
            }}
          />
          {/* No y-axis label. A rotated one clipped against the 288px plot
              ("How often the under wo"), and it only repeated the heading
              above the chart. The % on the ticks carries it. Domain is
              rounded out to multiples of 5 so the ticks read 40/45/50 rather
              than 39/46/53. */}
          <YAxis
            domain={[lo, hi]}
            ticks={ticks}
            tick={{ fill: AXIS, fontSize: 11 }}
            stroke={GRID}
            tickFormatter={(v) => `${v}%`}
            width={46}
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
              const d = item?.payload as (typeof data)[number];
              return [
                `${Number(value).toFixed(1)}% of unders won (${d.record})`,
                `${d.n} games`,
              ];
            }}
          />
          <ReferenceLine
            y={breakeven}
            stroke={AXIS}
            strokeDasharray="4 4"
            label={{
              value: `${breakeven}% — you break even here`,
              fill: AXIS,
              fontSize: 11,
              // insideTopLeft, not Right: the right-hand bars are the tall
              // green ones, and the label rendered dark-on-green there and was
              // unreadable. The space just above the line on the LEFT is empty
              // by definition — those bars are the ones below break-even.
              position: "insideTopLeft",
            }}
          />
          {/* isAnimationActive={false} is load-bearing, not a preference: under
              Recharts 3.8 the bars animate up from height 0, the animation
              never completes, and a zero-height rectangle renders as an empty
              group — a blank plot area beside a full table. Same trap as
              LineStudyView. */}
          <Bar
            dataKey="hitPct"
            isAnimationActive={false}
            radius={[2, 2, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
