"use client";

import { useState } from "react";
import { unitColor } from "@/lib/format";
import type { Record3 } from "@/lib/record";

// ONE breakdown table with a By week / By reason / By blocker toggle, replacing
// the three stacked tables that used to sit here (Tate 2026-09-13).
//
// They were the same 31 picks sliced three ways: "Week by week" and "By reason"
// were structurally identical (the same Real money / Paper column pair doubled)
// and "Paper record by what blocked it" was half of it. Three sets of column
// headers to learn, ~1,800px, for one small dataset.
//
// The blocker view deliberately drops the real-money columns rather than
// filling them with dashes: a blocker is the reason a real bet did NOT happen,
// so those cells could only ever be empty. `realBets === null` is what says a
// view is paper-only.

export type BreakdownRow = {
  key: string;
  label: string;
  /** null = this view has no real-money side (the blocker view). */
  realBets: number | null;
  real: Record3 | null;
  paperBets: number;
  paper: Record3 | null;
};

export type BreakdownView = {
  id: string;
  /** Toggle button text. */
  tab: string;
  /** Header for the first column. */
  head: string;
  caption: string;
  /** Shown in place of the table when there is nothing to show. */
  empty: string;
  rows: BreakdownRow[];
};

function RecCells({ rec }: { rec: Record3 | null }) {
  if (!rec) {
    return (
      <>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
        <td className="bv-num text-[var(--text-dim)]">—</td>
      </>
    );
  }
  return (
    <>
      <td className="bv-num font-mono text-[var(--text)]">{rec.record}</td>
      <td className="bv-num font-mono" style={{ color: unitColor(rec.units) }}>
        {rec.units}
      </td>
      <td className="bv-num font-mono text-[var(--text-muted)]">{rec.roi}</td>
      <td className="bv-num font-mono text-[var(--text-muted)]">{rec.clv}</td>
    </>
  );
}

function RecHead() {
  return (
    <>
      <th className="bv-num">W-L-P</th>
      <th className="bv-num">Units</th>
      <th className="bv-num">ROI</th>
      <th className="bv-num">Line value</th>
    </>
  );
}

export default function Breakdown({ views }: { views: BreakdownView[] }) {
  const [active, setActive] = useState(views[0]?.id ?? "");
  const view = views.find((v) => v.id === active) ?? views[0];
  if (!view) return null;
  const paperOnly = view.rows.every((r) => r.realBets === null);

  return (
    <section aria-label="Breakdown" className="mt-8">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text)]">Breakdown</h2>
        <div
          role="tablist"
          aria-label="Break the picks down by"
          className="flex flex-wrap gap-2"
        >
          {views.map((v) => (
            <button
              key={v.id}
              role="tab"
              aria-selected={v.id === view.id}
              onClick={() => setActive(v.id)}
              className="bv-chip"
            >
              {v.tab}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-3 max-w-3xl text-xs leading-relaxed text-[var(--text-dim)]">
        {view.caption}
      </p>

      {view.rows.length === 0 ? (
        <p className="bv-empty">{view.empty}</p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              {paperOnly ? (
                <tr>
                  <th>{view.head}</th>
                  <th className="bv-num">Picks</th>
                  <RecHead />
                </tr>
              ) : (
                <>
                  <tr>
                    <th
                      rowSpan={2}
                      className={view.id === "week" ? "bv-num" : ""}
                    >
                      {view.head}
                    </th>
                    <th colSpan={5}>Real money</th>
                    <th colSpan={5}>Paper</th>
                  </tr>
                  <tr>
                    <th className="bv-num">Bets</th>
                    <RecHead />
                    <th className="bv-num">Picks</th>
                    <RecHead />
                  </tr>
                </>
              )}
            </thead>
            <tbody>
              {view.rows.map((r) => (
                <tr key={r.key}>
                  <td
                    className={
                      view.id === "week"
                        ? "bv-num font-mono text-[var(--text)]"
                        : "text-[var(--text)]"
                    }
                  >
                    {r.label}
                  </td>
                  {r.realBets !== null && (
                    <>
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {r.realBets}
                      </td>
                      <RecCells rec={r.real} />
                    </>
                  )}
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {r.paperBets}
                  </td>
                  <RecCells rec={r.paper} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
