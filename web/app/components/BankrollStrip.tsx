import { usd } from "@/lib/format";
import type { Bankroll } from "@/lib/homeBoard";
import { WEEKLY_BET_CAP } from "@/lib/verdict";

// The discipline strip under the slip on Results: how much of the weekly cap
// is gone, the paper record, and the standing rules. On a phone it folds into
// one summary line; md+ shows the full grid. Amber marks a used-up cap.
// Green/red never appear here — outcomes are graded above, in the hero.
//
// The bankroll, unit size and season units used to sit here too. They are the
// hero now (BankrollHero), and saying them twice on one page made the money
// answer look like a footnote (Tate 2026-09-10).
//
// Copy rule (spec §10): every `title=` became a visible line under its value.
// A tooltip is unreachable on the phone this strip is mostly read on.

const NOTE = "max-w-56 text-xs leading-snug text-[var(--text-dim)]";

function Grid({ b }: { b: Bankroll }) {
  const capHit = b.weekBets >= b.cap;
  return (
    <>
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <div className="bv-stat">
          <span className="bv-stat-label">This week</span>
          <span
            className="bv-stat-value text-xl"
            style={{ color: capHit ? "var(--warn)" : "var(--text)" }}
          >
            {`${b.weekBets} / ${b.cap} bets`}
          </span>
          <span className="text-xs text-[var(--text-dim)]">
            {capHit
              ? "cap reached — nothing more this week"
              : "a ceiling, not a target"}
          </span>
          <span className={NOTE}>
            {`Real-money bets logged this week. ${WEEKLY_BET_CAP} is the ceiling.`}
          </span>
        </div>
        {b.paper && (
          <div className="bv-stat">
            <span className="bv-stat-label">Paper</span>
            <span className="bv-stat-value text-xl text-[var(--text-muted)]">
              {b.paper.record}
            </span>
            <span className="text-xs text-[var(--text-dim)]">{`${b.paper.hit} under · ${b.paper.units}u · line value ${b.paper.clv}`}</span>
            <span className={NOTE}>
              Picks tracked with no money on them, kept out of the real record.
            </span>
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
        {[
          "First-half unders only",
          `At most ${b.cap} bets a week`,
          `${usd(b.unitUsd)} a bet, always`,
          "Only games with a live Hard Rock line",
          "Check the injury list before every bet",
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
  // Leads with the cap: it is the one number on this strip that changes what
  // you are allowed to do next, and the bankroll is already large above it.
  const summary = `${b.weekBets} / ${b.cap} bets this week${
    b.weekBets >= b.cap ? " · cap reached" : ""
  }`;
  return (
    <div className="bv-card mb-6 p-4">
      <details className="md:hidden">
        <summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 font-mono text-sm text-[var(--text)]">
          <span>{summary}</span>
          <span aria-hidden="true" className="text-xs text-[var(--text-dim)]">
            ▾
          </span>
        </summary>
        <div className="mt-3">
          <Grid b={b} />
        </div>
      </details>
      <p className="text-xs text-[var(--text-dim)] md:hidden">
        Tap for the full strip.
      </p>
      <div className="hidden md:flex md:flex-col">
        <Grid b={b} />
      </div>
    </div>
  );
}
