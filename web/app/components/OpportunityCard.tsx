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
  const z = row.liveGapZ;
  // A gap only "counts" once it clears the BV line's own noise (|z| >= 1).
  const significant = z !== null && Math.abs(z) >= 1;
  // Positive gap (Vegas above our BV number) = an under-leaning gap — but grey it
  // out when it's within noise, so a noisy gap doesn't read as an edge.
  const gapColor =
    gap === null || !significant
      ? "#6b7280"
      : gap > 0
        ? "#65a30d"
        : "#dc2626";
  const qbOut = row.factors.qb_out_home || row.factors.qb_out_away;

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

        {qbOut && (
          <div
            className="mt-1 inline-block rounded-md border border-amber-700/60 bg-amber-950/40 px-2 py-0.5 text-xs text-amber-300"
            title={row.factors.qb_out_detail ?? "Starting QB listed out (live ESPN, unofficial). Not a model input."}
          >
            ⚠ QB OUT
            {row.factors.qb_out_away ? ` · ${row.away}` : ""}
            {row.factors.qb_out_home ? ` · ${row.home}` : ""}
            <span className="ml-1 text-amber-500/70">(live, unofficial)</span>
          </div>
        )}

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
          title="BV = our own MARKET-BLIND 1H projection (no Vegas number feeds it). The band is the 80% range — the BV line is noisy, so a gap only counts as a signal once it clears ~1σ. Gaps within the band are noise, not edges. Validated only by the CLV-by-gap table in Research."
        >
          BV {row.bvLine !== null ? row.bvLine.toFixed(1) : "—"}
          {row.bvLo !== null && row.bvHi !== null && (
            <span className="text-gray-600">
              {" "}({row.bvLo.toFixed(0)}–{row.bvHi.toFixed(0)})
            </span>
          )}
          <span className="text-gray-600"> · </span>
          Vegas {vegas !== null ? vegas.toFixed(1) : "—"}
          <span className="text-gray-600"> · gap </span>
          <span style={{ color: gapColor }}>
            {gap !== null ? `${gap > 0 ? "+" : ""}${gap.toFixed(1)}` : "—"}
          </span>
          {z !== null && (
            <span className={significant ? "text-gray-300" : "text-gray-600"}>
              {" "}({z > 0 ? "+" : ""}{z.toFixed(1)}σ{significant ? "" : " · noise"})
            </span>
          )}
          {row.bvAdjust !== null && (
            <span
              className="ml-1 text-amber-400"
              title={row.bvAdjustReason ?? "manual BV adjustment"}
            >
              (adj {row.bvAdjust > 0 ? "+" : ""}{row.bvAdjust}
              {row.bvAdjustReason ? `: ${row.bvAdjustReason}` : ""})
            </span>
          )}
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
