"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import type { BandRow } from "@/lib/postmortem";

// THE finding, as a picture: the wider the gap between Hard Rock's first-half
// line and our number, the more often the under wins. Since 2026-09-16 the
// chart carries the numbers the band table used to hold — the rate on each
// bar, games and units under each band — so the table no longer follows it
// (Tate: "a chart that needs a paragraph has already failed"; one that needs a
// table under it is the same failure).
//
// Approved on the rule "if it isn't obvious I don't want it": the bars climb
// left to right, the ones that make money are green, and the break-even line
// is drawn and labelled.

// Recharts takes colour strings, not CSS variables — same literals as
// LineStudyView, from the design tokens.
const AXIS = "#aab6cc"; // --text-muted
const DIM = "#8b98b0"; // --text-dim
const GRID = "#3a4a6b"; // --border
const GOOD = "#3ddc84"; // --good
const BAD = "#f87171"; // --bad
const INK = "#04121f"; // --badge-ink, on a filled bar

/** Rows thinner than this say nothing; they plot, but greyed. */
const THIN = "#6b7a99";

type Datum = {
  bucket: string;
  hitPct: number;
  n: number;
  units: string;
  fill: string;
};

/** Two-line category tick: the band, then games · units. */
function BandTick({
  x,
  y,
  payload,
  byBucket,
}: {
  x?: number;
  y?: number;
  payload?: { value: string };
  byBucket: Map<string, Datum>;
}) {
  const d = payload ? byBucket.get(payload.value) : undefined;
  return (
    <g transform={`translate(${x ?? 0},${y ?? 0})`}>
      <text
        x={0}
        y={0}
        dy={14}
        textAnchor="middle"
        fill={AXIS}
        fontSize={12}
        fontWeight={600}
      >
        {payload?.value}
      </text>
      {/* Games and units on their own lines: side by side they collided at
          390px, where five bands share ~300px. */}
      {d && (
        <>
          <text
            x={0}
            y={0}
            dy={29}
            textAnchor="middle"
            fill={DIM}
            fontSize={11}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {d.n.toLocaleString()}
          </text>
          <text
            x={0}
            y={0}
            dy={43}
            textAnchor="middle"
            fill={DIM}
            fontSize={11}
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {`${Number(d.units) >= 0 ? "+" : ""}${Number(d.units).toFixed(1)}u`}
          </text>
        </>
      )}
    </g>
  );
}

export default function GapLadderChart({
  rows,
  breakeven,
}: {
  rows: BandRow[];
  breakeven: number;
}) {
  const data: Datum[] = rows
    .filter((r) => r.hitPct !== null)
    .map((r) => ({
      bucket: r.bucket,
      hitPct: r.hitPct as number,
      n: r.n,
      units: r.units,
      // A band under 30 games is a count, not a rate; colouring it green would
      // promise an edge the sample cannot support.
      fill:
        r.size === "small"
          ? THIN
          : (r.hitPct as number) >= breakeven
            ? GOOD
            : BAD,
    }));
  if (data.length === 0) return null;
  const byBucket = new Map(data.map((d) => [d.bucket, d]));

  const maxPct = data.reduce((m, d) => Math.max(m, d.hitPct), 0);
  const minPct = data.reduce((m, d) => Math.min(m, d.hitPct), 100);
  // Round the axis out to whole 5s and tick it by hand. Recharts' own choice
  // inside a tight domain came out 40/47/54/61/65, which reads like an
  // accident rather than a scale. Extra headroom at the top for the labels.
  const lo = Math.max(0, Math.floor((minPct - 4) / 5) * 5);
  const hi = Math.ceil((maxPct + 7) / 5) * 5;
  const ticks: number[] = [];
  for (let t = lo; t <= hi; t += 5) ticks.push(t);

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, bottom: 22, left: 0 }}
        >
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="bucket"
            stroke={GRID}
            tickLine={false}
            interval={0}
            height={56}
            tick={<BandTick byBucket={byBucket} />}
          />
          {/* No y-axis label: the % on the ticks carries it. */}
          <YAxis
            domain={[lo, hi]}
            ticks={ticks}
            tick={{ fill: AXIS, fontSize: 11 }}
            stroke={GRID}
            tickFormatter={(v) => `${v}%`}
            width={44}
          />
          <ReferenceLine
            y={breakeven}
            stroke={AXIS}
            strokeDasharray="4 4"
            label={{
              value: `${breakeven}% break-even`,
              fill: AXIS,
              fontSize: 11,
              // Below the line at the left: the bars there are the short red
              // ones, so that strip is empty by definition, and the bar values
              // sit INSIDE their bars so nothing else is drawn there. Above the
              // line at the right it rendered dark-on-green.
              position: "insideBottomLeft",
            }}
          />
          {/* isAnimationActive={false} is load-bearing: under Recharts 3 the
              bars animate up from height 0, the animation never completes,
              and a zero-height rectangle renders as an empty group. */}
          <Bar dataKey="hitPct" isAnimationActive={false} radius={[2, 2, 0, 0]}>
            {/* Inside the bar, in badge ink: the shortest bar is ~30px tall
                at this domain, room for one 12px line, and it keeps the space
                above the bars free for the break-even label. */}
            <LabelList
              dataKey="hitPct"
              position="insideTop"
              fill={INK}
              fontSize={12}
              fontWeight={700}
              offset={6}
              formatter={(v: unknown) => `${Number(v).toFixed(1)}%`}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
