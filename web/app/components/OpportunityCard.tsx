import { BoardRow } from "@/lib/board";
import { buildChips, scoreColor } from "@/lib/score";

export default function OpportunityCard({ row }: { row: BoardRow }) {
  const color = scoreColor(row.underScore);
  const chips = buildChips(row.factors);

  // Current line: consensus current, else the line baked into factors at scoring.
  const line = row.curLine ?? row.factors.line ?? null;
  const showMove =
    row.openLine !== null &&
    row.curLine !== null &&
    Math.abs(row.openLine - row.curLine) >= 0.01;

  // Vegas line for the gap: live consensus, else the line at scoring time.
  const vegas = row.curLine ?? row.factors.line ?? null;
  const gap = row.liveGap;
  // Positive gap (Vegas above our BV number) = an under-leaning gap.
  const gapColor =
    gap === null ? "#6b7280" : gap > 0 ? "#65a30d" : gap < 0 ? "#dc2626" : "#9ca3af";

  return (
    <div className="flex gap-4 rounded-xl border border-gray-800 bg-gray-950 p-4">
      {/* Left: score */}
      <div className="flex w-24 shrink-0 flex-col items-center justify-center">
        <span className="text-[3rem] font-bold leading-none" style={{ color }}>
          {row.underScore ?? "—"}
        </span>
        <span className="mt-1 text-sm text-gray-400">#{row.rank ?? "—"}</span>
        <span className="text-xs text-gray-600">50 = BE</span>
      </div>

      {/* Right: matchup + details + chips */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="truncate text-lg font-semibold text-gray-100">
            {row.away} <span className="text-gray-500">@</span> {row.home}
          </h3>
          <span className="shrink-0 text-xs text-gray-500">Wk {row.week}</span>
        </div>

        <div className="mt-1 text-sm text-gray-300">
          Current 1H line: {line !== null ? line.toFixed(1) : "—"}
          {showMove && (
            <span className="ml-2 text-gray-500">
              ({row.openLine!.toFixed(1)} → {row.curLine!.toFixed(1)})
            </span>
          )}
        </div>

        <div
          className="mt-0.5 text-sm text-gray-300"
          title="BV = the model's own calibrated 1H projection vs the market. Positive gap = Vegas above our number (under-leaning). Large gaps can be model blind spots, not edges — see the CLV-by-gap table in Research."
        >
          BV {row.bvLine !== null ? row.bvLine.toFixed(1) : "—"}
          <span className="text-gray-600"> · </span>
          Vegas {vegas !== null ? vegas.toFixed(1) : "—"}
          <span className="text-gray-600"> · gap </span>
          <span style={{ color: gapColor }}>
            {gap !== null ? `${gap > 0 ? "+" : ""}${gap.toFixed(1)}` : "—"}
          </span>
        </div>

        <div className="text-sm text-gray-400">
          Model:{" "}
          {row.underProb !== null
            ? `under ${Math.round(row.underProb * 100)}%`
            : "—"}
        </div>

        <div className="mt-2 flex flex-wrap gap-1.5">
          {chips.map((c) => (
            <span
              key={c.label}
              title={c.hint}
              className="inline-flex items-center gap-1 rounded-full border border-gray-700 bg-gray-800 px-2.5 py-0.5 text-[0.82rem] text-gray-200"
            >
              <b className="text-gray-400">{c.label}</b>
              {c.value}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
