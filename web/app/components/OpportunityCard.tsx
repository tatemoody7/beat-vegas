import { BoardRow } from "@/lib/board";
import { bookLabel } from "@/lib/books";
import type { Movement } from "@/lib/movement";
import { BET_GAP_PTS } from "@/lib/verdict";
import MovementChart from "@/app/components/MovementChart";
import {
  BoardFactor,
  buildChips,
  factorTint,
  groupFactorBoard,
  scoreColor,
  scoreLabel,
} from "@/lib/score";

const TIER_DOT: Record<number, string> = {
  1: "var(--accent)",
  2: "#5b6b8c",
  3: "#46506b",
  0: "#e0a44a", // hypotheses
};

function FactorRow({ f }: { f: BoardFactor }) {
  const tint = factorTint(f);
  // position marker: under-favorable lean to the right, clamped to ±2 spreads.
  const pct = Math.max(
    4,
    Math.min(96, 50 + (Math.max(-2, Math.min(2, f.lean)) / 2) * 50),
  );
  const text = f.sentence || `${f.label} — ${f.value}`;
  return (
    <div className="bv-fac-row" style={{ background: tint.bg }}>
      <span className="bv-fac-text">{text}</span>
      {f.hypothesis ? (
        <span
          className="bv-fac-badge bv-fac-badge-amber"
          title="Tracks more 1H scoring on the proxy; unproven on real lines."
        >
          ⚠ unproven
        </span>
      ) : f.live ? (
        <span
          className={`bv-fac-badge ${f.live.cooling ? "bv-fac-badge-amber" : "bv-fac-badge-live"}`}
          title={
            f.live.cooling
              ? "Real-line under record when green — but the recent window has cooled below breakeven."
              : "Real-line first-half under record when this factor is green."
          }
        >
          {f.live.cooling ? "❄ " : ""}n={f.live.n} ·{" "}
          {Math.round(f.live.mean * 100)}% ±
          {Math.round(((f.live.hi - f.live.lo) / 2) * 100)}
        </span>
      ) : (
        <span className="bv-fac-badge">no live data yet</span>
      )}
      <span className="bv-fac-track" aria-hidden>
        <span
          className="bv-fac-track-dot"
          style={{ left: `${pct}%`, background: tint.dot }}
        />
      </span>
    </div>
  );
}

// Line-movement history for the card, as an expandable row (one query for the
// whole week in lib/movement.ts::getMovements).
function MovementRow({ m }: { m: Movement }) {
  return (
    <details className="mt-3 rounded-md border border-[var(--border-soft)] bg-[var(--bg-2)] px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-[var(--text-muted)]">
        {`Line movement · ${m.rows.length} updates across ${m.books.length} book${m.books.length === 1 ? "" : "s"}`}
      </summary>
      <div className="mt-2 flex flex-col gap-3">
        <MovementChart points={m.points} books={m.books} />
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>When checked (ET)</th>
                <th>Sportsbook</th>
                <th>1H line</th>
              </tr>
            </thead>
            <tbody>
              {m.rows.map((r, i) => (
                <tr key={i}>
                  <td className="text-[var(--text-muted)]">{r.captured_at}</td>
                  <td className="text-[var(--text-muted)]">
                    {bookLabel(r.book)}
                  </td>
                  <td className="font-mono text-[var(--text)]">{r.line}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}

export default function OpportunityCard({
  row,
  movement = null,
}: {
  row: BoardRow;
  movement?: Movement | null;
}) {
  const color = scoreColor(row.underScore);
  const chips = buildChips(row.factors);
  const tierGroups = groupFactorBoard(row.factors.factor_board);

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
  // It's a real market number only when a live consensus exists; otherwise the
  // fallback is an estimate (e.g. the proxy line baked in at scoring time).
  const vegasIsLive = row.curLine !== null;
  const gap = row.liveGap;
  // A gap "counts" once it reaches the validated bettable band (top ~20% of a
  // season's gaps, in points). sigma (~12 pts) is per-game outcome noise and can
  // never be cleared, so it is not the test here.
  const significant = gap !== null && Math.abs(gap) >= BET_GAP_PTS;
  // Positive gap (Vegas above our BV number) = an under-leaning gap — grey it
  // out below the bettable band so a small gap doesn't read as an edge.
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
                  "Starting QB listed out (live Rotowire, unofficial). Not a model input."
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
                  title={
                    vegasIsLive
                      ? "The sportsbook's first-half points total right now."
                      : "Estimated first-half line (proxy from the full-game total) — no live market line captured for this game yet."
                  }
                >
                  <span className="bv-stat-label">
                    {vegasIsLive ? "Vegas" : "Est. line"}
                  </span>
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
                  title={`Edge vs Vegas: how far the Vegas line sits above our number, in points. Gaps of ${BET_GAP_PTS}+ points are the top ~20% of a season — the ranking band the backtest validated, not a proven win rate (against a fair estimated line it showed no confirmed edge; only real-line closing-line value can). Smaller gaps are a lean, not a bet.`}
                >
                  <span className="bv-stat-label">Edge vs Vegas</span>
                  <span className="bv-stat-value" style={{ color: gapColor }}>
                    {gap !== null
                      ? `${gap > 0 ? "+" : ""}${gap.toFixed(1)}`
                      : "—"}
                    {gap !== null && (
                      <span
                        className={`ml-1 text-xs font-normal ${significant ? "text-[var(--text-muted)]" : "text-[var(--text-dim)]"}`}
                      >
                        {significant
                          ? gap > 0
                            ? "bettable band"
                            : "leans over"
                          : "small lean"}
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

          {movement && movement.points.length > 1 && (
            <MovementRow m={movement} />
          )}

          {/* Green/red factor board — the story behind the rank (explainer
              only; never moves it). Falls back to the legacy chips until a
              card has a factor_board payload. */}
          {!derived && tierGroups.length > 0 ? (
            <div className="mt-3">
              {tierGroups.map((g) => (
                <div key={g.tier}>
                  <div className="bv-fac-tier">
                    <span
                      className="bv-fac-tier-dot"
                      style={{ background: TIER_DOT[g.tier] }}
                    />
                    {g.title}
                  </div>
                  {g.factors.map((f) => (
                    <FactorRow key={f.key} f={f} />
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {chips.map((c) => (
                <span key={c.label} title={c.hint} className="bv-pill">
                  <span className="bv-pill-label">{c.label}</span>
                  <span className="bv-pill-value">{c.value}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
