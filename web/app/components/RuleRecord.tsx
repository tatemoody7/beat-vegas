import { unitColor } from "@/lib/format";
import type { Record3 } from "@/lib/record";
import { EmptyLine } from "@/app/components/Section";

// The scoreboard, at the top of Results: the paper record of the rule itself --
// every game the card qualified (gap >= 1.75 at Hard Rock's number), logged at
// Hard Rock's line and price with one flat unit, uncapped, as the card logged it
// (Tate 2026-09-15: the paper ledger is the scoreboard; real money is the
// discipline test and sits below under "Did I follow it").
//
// Same layout as BankrollHero so the two read as one page: the hit rate at
// display size with its 95% Wilson interval and W-L beneath, then n, line value,
// and paper units + ROI. Nothing here needs a caption to be read (Tate: "if it
// isn't obvious I don't want it"). No chart.

const pct = (v: number) => `${(100 * v).toFixed(1)}%`;

export default function RuleRecord({ rec }: { rec: Record3 | null }) {
  if (rec === null) {
    return (
      <section aria-label="The rule, on paper" className="bv-card mb-6 p-5">
        <span className="bv-stat-label">The rule, on paper</span>
        <EmptyLine className="mt-2">
          The rule’s record fills in as the card’s paper picks grade.
        </EmptyLine>
      </section>
    );
  }
  const interval =
    rec.hitLo === null || rec.hitHi === null
      ? "nothing decided yet"
      : `95% interval ${pct(rec.hitLo)}–${pct(rec.hitHi)}`;
  return (
    <section aria-label="The rule, on paper" className="bv-card mb-6 p-5">
      <span className="bv-stat-label">The rule, on paper</span>
      <div className="mt-1 flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <span className="bv-stat-label">Hit rate</span>
          <p className="mt-1 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
            {rec.hit}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            {`${interval} · ${rec.record}`}
          </p>
        </div>
        <div>
          <span className="bv-stat-label">Picks</span>
          <p className="mt-1 font-mono text-3xl font-semibold leading-none tabular-nums text-[var(--text-muted)]">
            {rec.n}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            graded paper picks, one flat unit each
          </p>
        </div>
        <div>
          <span className="bv-stat-label">Line value</span>
          <p className="mt-1 font-mono text-3xl font-semibold leading-none tabular-nums text-[var(--text-muted)]">
            {rec.clv}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            points the market came toward us; + is good
          </p>
        </div>
        <div>
          <span className="bv-stat-label">Units</span>
          <p
            className="mt-1 font-mono text-3xl font-semibold leading-none tabular-nums"
            style={{ color: unitColor(rec.units) }}
          >
            {`${rec.units}u`}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            {`ROI ${rec.roi} · units won ÷ units risked`}
          </p>
        </div>
      </div>
    </section>
  );
}
