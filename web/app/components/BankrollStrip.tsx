import type { Bankroll } from "@/lib/homeBoard";

// Bankroll + discipline strip on the home board. On a phone it folds into one
// summary line (the slip sits above it on Saturday morning); md+ shows the
// full grid. Cyan is the brand accent; amber marks a used-up cap. Green/red
// never appear here — outcomes are graded on the ledger, not the strip.
const usd = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

const signedUnits = (u: number) => `${u > 0 ? "+" : ""}${u.toFixed(2)}u`;

function Grid({ b }: { b: Bankroll }) {
  const capHit = b.weekBets >= b.cap;
  return (
    <>
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div
          className="bv-stat"
          title="Starting bankroll plus settled real-money units × unit size."
        >
          <span className="bv-stat-label">Bankroll</span>
          <span className="bv-stat-value text-xl">{usd(b.currentUsd)}</span>
          <span className="text-xs text-[var(--text-dim)]">{`started ${usd(b.startUsd)}`}</span>
        </div>
        <div
          className="bv-stat"
          title="Every bet is exactly one unit. Flat staking keeps results readable."
        >
          <span className="bv-stat-label">1 unit</span>
          <span className="bv-stat-value text-xl">{usd(b.unitUsd)}</span>
          <span className="text-xs text-[var(--text-dim)]">
            flat, every bet
          </span>
        </div>
        <div
          className="bv-stat"
          title="Profit or loss in units on settled real-money first-half bets this season. ROI = units won ÷ units staked."
        >
          <span className="bv-stat-label">Season</span>
          <span className="bv-stat-value text-xl text-[var(--text)]">
            {signedUnits(b.realUnits)}
          </span>
          <span className="text-xs text-[var(--text-dim)]">
            {b.real
              ? `${b.real.record} · ${b.real.hit} under · ROI ${b.real.roi}`
              : "no settled bets yet"}
          </span>
        </div>
        <div
          className="bv-stat"
          title="Real-money bets logged this week against the weekly cap. Zero is a fine week."
        >
          <span className="bv-stat-label">This week</span>
          <span
            className="bv-stat-value text-xl"
            style={{ color: capHit ? "var(--warn)" : "var(--text)" }}
          >
            {`${b.weekBets} / ${b.cap} bets`}
          </span>
          <span className="text-xs text-[var(--text-dim)]">
            {capHit ? "cap reached — no more this week" : "cap, not a target"}
          </span>
        </div>
        {b.paper && (
          <div
            className="bv-stat"
            title="Paper picks: tracked with nothing at risk, kept apart from the real record."
          >
            <span className="bv-stat-label">Paper</span>
            <span className="bv-stat-value text-xl text-[var(--text-muted)]">
              {b.paper.record}
            </span>
            <span className="text-xs text-[var(--text-dim)]">{`${b.paper.hit} under · ${b.paper.units}u · line value ${b.paper.clv}`}</span>
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        {[
          "First-half unders only",
          `At most ${b.cap} bets a week`,
          "Flat 1 unit per bet",
          "Only BET cards with a live line",
          "Check injuries before every bet",
        ].map((rule) => (
          <span key={rule} className="bv-pill">
            <span className="bv-pill-value">{rule}</span>
          </span>
        ))}
      </div>
    </>
  );
}

export default function BankrollStrip({ b }: { b: Bankroll }) {
  const summary = `${usd(b.currentUsd)} · ${signedUnits(b.realUnits)} · ${b.weekBets}/${b.cap} this week`;
  return (
    <div className="bv-card mb-6 p-4">
      <details className="md:hidden">
        <summary
          className="flex min-h-11 cursor-pointer items-center justify-between gap-2 font-mono text-sm text-[var(--text)]"
          title="Bankroll, season units and this week’s bets against the cap. Tap for the full strip."
        >
          <span>{summary}</span>
          <span aria-hidden="true" className="text-xs text-[var(--text-dim)]">
            ▾
          </span>
        </summary>
        <div className="mt-3">
          <Grid b={b} />
        </div>
      </details>
      <div className="hidden md:flex md:flex-col">
        <Grid b={b} />
      </div>
    </div>
  );
}
