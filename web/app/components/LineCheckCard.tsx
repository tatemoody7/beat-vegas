"use client";

import { useState } from "react";
import type { EvVerdict, LineCheckRow, Verdict } from "@/lib/lineCheck";

import { bookLabel as label } from "@/lib/books";

// Verdict drives the pill. Good under value = HR at/above the best total. Reuses
// the under/over semantic tokens (the verdict is about under favorability), not a
// new UI accent.
const VERDICT: Record<Verdict, { text: string; color: string; blurb: string }> =
  {
    good: {
      text: "Good line",
      color: "var(--under-strong)",
      blurb: "Hard Rock is at or above the best total in the market.",
    },
    fair: {
      text: "Fair line",
      color: "var(--neutral)",
      blurb: "Within half a point of the best available total.",
    },
    poor: {
      text: "Poor line",
      color: "var(--over)",
      blurb: "Hard Rock is shading the total down vs the field.",
    },
    "no-hr": {
      text: "No HR line yet",
      color: "var(--text-dim)",
      blurb: "Hard Rock hasn't posted this game yet.",
    },
  };

// EV verdict is a separate axis from line quality: does HR's under PRICE clear
// the market's no-vig fair-under at this number? Cyan = the brand accent (we
// reserve green/red for under/over outcomes), neutral/dim for the rest.
const EV: Record<EvVerdict, { text: string; color: string; blurb: string }> = {
  pos: {
    text: "+EV price",
    color: "var(--accent)",
    blurb:
      "Hard Rock's under price beats the market's no-vig fair price at this number.",
  },
  fair: {
    text: "Fair price",
    color: "var(--neutral)",
    blurb:
      "Hard Rock's under is priced about in line with the market once the vig is removed.",
  },
  neg: {
    text: "Pays the vig",
    color: "var(--text-muted)",
    blurb:
      "Hard Rock's under price sits below the market's no-vig fair price beyond the standard vig.",
  },
  na: {
    text: "No price yet",
    color: "var(--text-dim)",
    blurb: "Not enough two-sided prices at a comparable number to judge EV.",
  },
};

const pct1 = (x: number | null) =>
  x === null ? "—" : `${(100 * x).toFixed(1)}%`;
const signedPct1 = (x: number | null) =>
  x === null ? "—" : `${x >= 0 ? "+" : ""}${(100 * x).toFixed(1)}%`;

export default function LineCheckCard({ row }: { row: LineCheckRow }) {
  const [open, setOpen] = useState(false);
  const v = VERDICT[row.verdict];
  const ev = EV[row.evVerdict];

  return (
    <div className="bv-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="bv-pill mb-1">Week {row.week}</span>
          <div className="truncate text-base font-semibold text-[var(--text)]">
            {row.matchup}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {row.evVerdict !== "na" && (
            <span
              className="bv-pill"
              style={{ color: ev.color, borderColor: ev.color }}
              title={ev.blurb}
            >
              {ev.text}
            </span>
          )}
          <span
            className="bv-pill"
            style={{ color: v.color, borderColor: v.color }}
            title={v.blurb}
          >
            {v.text}
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        <div className="bv-stat">
          <div className="bv-stat-label">Hard Rock</div>
          <div className="bv-stat-value" style={{ color: v.color }}>
            {row.hrLine ?? "—"}
          </div>
        </div>
        <div className="bv-stat">
          <div className="bv-stat-label">Best available</div>
          <div className="bv-stat-value">{row.best ?? "—"}</div>
        </div>
        <div className="bv-stat">
          <div className="bv-stat-label">Market median</div>
          <div className="bv-stat-value">{row.median ?? "—"}</div>
        </div>
      </div>

      {row.hrFairUnder !== null && (
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--text-muted)]">
          <span title="Hard Rock's no-vig fair under probability (de-vigged from its two-sided price).">
            HR no-vig under{" "}
            <span className="font-mono text-[var(--text)]">
              {pct1(row.hrFairUnder)}
            </span>
          </span>
          <span title="Hard Rock's two-way hold (the vig baked into its over/under prices).">
            hold{" "}
            <span className="font-mono text-[var(--text)]">
              {pct1(row.hrHold)}
            </span>
          </span>
          {row.ev !== null && (
            <span title="Per-$1 EV of HR's under vs the market no-vig fair-under at a comparable number.">
              EV{" "}
              <span className="font-mono" style={{ color: ev.color }}>
                {signedPct1(row.ev)}
              </span>
            </span>
          )}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-[var(--text-muted)]">
          {row.hrLine !== null && row.delta !== null
            ? row.delta === 0
              ? "HR has the best number."
              : `HR is ${Math.abs(row.delta)} below the best.`
            : "Waiting on Hard Rock."}
        </span>
        <button
          type="button"
          className="bv-nav-link"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
        >
          {open ? "Hide books" : `All books (${row.books.length})`}
        </button>
      </div>

      {open && (
        <div className="bv-table-wrap mt-3">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Sportsbook</th>
                <th>Total</th>
                <th>vs best</th>
              </tr>
            </thead>
            <tbody>
              {row.books.map((b) => {
                const d =
                  row.best !== null
                    ? Number((b.line - row.best).toFixed(2))
                    : null;
                return (
                  <tr
                    key={b.book}
                    style={
                      b.isHR
                        ? {
                            background:
                              "color-mix(in srgb, var(--accent) 12%, transparent)",
                          }
                        : undefined
                    }
                  >
                    <td className="text-[var(--text)]">
                      {label(b.book)}
                      {b.isHR ? " ★" : ""}
                    </td>
                    <td className="font-mono text-[var(--text)]">{b.line}</td>
                    <td className="font-mono text-[var(--text-muted)]">
                      {d === null || d === 0 ? "—" : d}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
