import { BoardRow } from "@/lib/board";
import { buildChips, scoreColor, scoreLabel } from "@/lib/score";

export default function OpportunityCard({ row }: { row: BoardRow }) {
  const color = scoreColor(row.underScore);
  const chips = buildChips(row.factors);

  // Derived-line card: our 1H number off the posted full-game line, no model.
  const derived = row.factors.line_kind === "derived_fg";
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
    gap === null || !significant ? "#6b7280" : gap > 0 ? "#65a30d" : "#dc2626";
  const qbOut = row.factors.qb_out_home || row.factors.qb_out_away;

  return (
    <div className="bv-card bv-card-interactive overflow-hidden">
      {/* Score-strength rail (hidden on reference cards — no pick) */}
      {!derived && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-1.5"
          style={{ backgroundColor: color }}
        />
      )}

      <div className="flex gap-4 p-4 pl-5">
        {/* Left: hero under score — or "no pick" on reference-line cards */}
        {derived ? (
          <div className="flex w-24 shrink-0 flex-col items-center justify-center text-center text-[var(--text-dim)]">
            <span className="text-sm">no pick</span>
          </div>
        ) : (
          <div className="flex w-24 shrink-0 flex-col items-center justify-center text-center">
            <span
              className="font-[family-name:var(--font-display)] text-[3.25rem] font-extrabold leading-none tabular-nums"
              style={{ color }}
              title="Under score, 0–100: how strongly we lean under. 50 = a coin flip after the vig; higher = a stronger under lean."
            >
              {row.underScore ?? "—"}
            </span>
            <span
              className="mt-1.5 text-[0.7rem] font-semibold uppercase tracking-wide"
              style={{ color }}
            >
              {scoreLabel(row.underScore)}
            </span>
            <span className="mt-0.5 text-xs text-[var(--text-dim)]">
              #{row.rank ?? "—"} · 50 = coin flip
            </span>
          </div>
        )}

        {/* Right: matchup + stat row + chips */}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="truncate text-lg font-semibold text-[var(--text)]">
              {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
              {row.home}
            </h3>
            <span className="shrink-0 rounded-md bg-[var(--surface-2)] px-2 py-0.5 text-xs font-medium text-[var(--text-muted)]">
              Wk {row.week}
            </span>
          </div>

          {/* Status badges */}
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {derived && (
              <span
                className="inline-block rounded-md border border-sky-700/60 bg-sky-950/40 px-2 py-0.5 text-xs text-sky-300"
                title="Our spread-adjusted first-half number worked out from the posted full-game line. It's a reference point, not a model pick, and it isn't graded — there's no score or edge."
              >
                Reference line — no pick
              </span>
            )}
            {qbOut && (
              <span
                className="inline-block rounded-md border border-amber-700/60 bg-amber-950/40 px-2 py-0.5 text-xs text-amber-300"
                title={
                  row.factors.qb_out_detail ??
                  "Starting QB listed out (live ESPN, unofficial). Not a model input."
                }
              >
                ⚠ QB OUT
                {row.factors.qb_out_away ? ` · ${row.away}` : ""}
                {row.factors.qb_out_home ? ` · ${row.home}` : ""}
                <span className="ml-1 text-amber-500/70">
                  (live, unofficial)
                </span>
              </span>
            )}
          </div>

          {derived ? (
            <div className="mt-2 text-sm text-[var(--text-muted)]">
              Reference 1st-half line:{" "}
              <span className="font-mono font-semibold text-[var(--text)]">
                {line !== null ? line.toFixed(1) : "—"}
              </span>
              {row.factors.full_game_total !== null &&
                row.factors.full_game_total !== undefined && (
                  <span className="text-[var(--text-dim)]">
                    {" "}
                    · from full-game total{" "}
                    {row.factors.full_game_total.toFixed(1)}
                    {row.factors.spread !== null &&
                    row.factors.spread !== undefined
                      ? ` (${row.factors.spread > 0 ? "+" : ""}${row.factors.spread.toFixed(1)})`
                      : ""}
                  </span>
                )}
            </div>
          ) : (
            <>
              {/* Stat row — the three numbers that matter, scannable */}
              <div className="mt-2.5 flex flex-wrap items-end gap-x-6 gap-y-2">
                <div
                  className="bv-stat"
                  title="Our number is the model's own predicted first-half total — it never looks at the Vegas line. The range is its margin of error; an edge inside that margin isn't a real signal."
                >
                  <span className="bv-stat-label">Our number</span>
                  <span className="bv-stat-value">
                    {row.bvLine !== null ? row.bvLine.toFixed(1) : "—"}
                    {row.bvLo !== null && row.bvHi !== null && (
                      <span className="ml-1 text-xs font-normal text-[var(--text-dim)]">
                        {row.bvLo.toFixed(0)}–{row.bvHi.toFixed(0)}
                      </span>
                    )}
                    {row.bvAdjust !== null && (
                      <span
                        className="ml-1 text-xs font-normal text-amber-400"
                        title={
                          row.bvAdjustReason ??
                          "manual adjustment to our number"
                        }
                      >
                        (adj {row.bvAdjust > 0 ? "+" : ""}
                        {row.bvAdjust})
                      </span>
                    )}
                  </span>
                </div>

                <div
                  className="bv-stat"
                  title="The sportsbook's first-half points total right now."
                >
                  <span className="bv-stat-label">Vegas</span>
                  <span className="bv-stat-value">
                    {vegas !== null ? vegas.toFixed(1) : "—"}
                    {showMove && (
                      <span className="ml-1 text-xs font-normal text-[var(--text-dim)]">
                        ({row.openLine!.toFixed(1)}→{row.curLine!.toFixed(1)})
                      </span>
                    )}
                  </span>
                </div>

                <div
                  className="bv-stat"
                  title="Edge vs Vegas: how far the Vegas line sits above our number. Only a 'clear signal' once it clears our model's own margin of error."
                >
                  <span className="bv-stat-label">Edge vs Vegas</span>
                  <span className="bv-stat-value" style={{ color: gapColor }}>
                    {gap !== null
                      ? `${gap > 0 ? "+" : ""}${gap.toFixed(1)}`
                      : "—"}
                    {z !== null && (
                      <span
                        className={`ml-1 text-xs font-normal ${significant ? "text-[var(--text-muted)]" : "text-[var(--text-dim)]"}`}
                      >
                        {significant ? "clear signal" : "within normal range"}
                      </span>
                    )}
                  </span>
                </div>

                <div
                  className="bv-stat"
                  title="The model's estimated chance the first half stays under the line."
                >
                  <span className="bv-stat-label">Chance under</span>
                  <span className="bv-stat-value">
                    {row.underProb !== null
                      ? `${Math.round(row.underProb * 100)}%`
                      : "—"}
                  </span>
                </div>
              </div>
            </>
          )}

          {/* Detail chips */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <span key={c.label} title={c.hint} className="bv-pill">
                <span className="bv-pill-label">{c.label}</span>
                <span className="bv-pill-value">{c.value}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
