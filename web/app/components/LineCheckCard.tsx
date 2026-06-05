"use client";

import { useState } from "react";
import type { LineCheckRow, Verdict } from "@/lib/lineCheck";

const BOOK_LABELS: Record<string, string> = {
  hardrockbet: "Hard Rock",
  hardrockbet_fl: "Hard Rock (FL)",
  draftkings: "DraftKings",
  fanduel: "FanDuel",
  betmgm: "BetMGM",
  betrivers: "BetRivers",
  bovada: "Bovada",
  betparx: "betPARX",
  ballybet: "Bally Bet",
  betonlineag: "BetOnline",
  lowvig: "LowVig",
  espnbet: "ESPN Bet",
  caesars: "Caesars",
};

const label = (b: string) => BOOK_LABELS[b] ?? b;

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

export default function LineCheckCard({ row }: { row: LineCheckRow }) {
  const [open, setOpen] = useState(false);
  const v = VERDICT[row.verdict];

  return (
    <div className="bv-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <span className="bv-pill mb-1">Week {row.week}</span>
          <div className="truncate text-base font-semibold text-[var(--text)]">
            {row.matchup}
          </div>
        </div>
        <span
          className="bv-pill"
          style={{ color: v.color, borderColor: v.color }}
          title={v.blurb}
        >
          {v.text}
        </span>
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
                const d = row.best !== null ? Number((b.line - row.best).toFixed(2)) : null;
                return (
                  <tr
                    key={b.book}
                    style={
                      b.isHR
                        ? { background: "color-mix(in srgb, var(--accent) 12%, transparent)" }
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
