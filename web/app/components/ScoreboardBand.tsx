import { unitColor, usd } from "@/lib/format";
import type { Bankroll, BankrollPoint } from "@/lib/homeBoard";
import type { Record3 } from "@/lib/record";
import BankrollCurve from "@/app/components/BankrollCurve";
import { EmptyLine } from "@/app/components/Section";

// The top of Results: the three numbers that answer the page's question, in
// one card, with the bankroll curve beneath them (Concept A "Scoreboard",
// Tate 2026-09-16). It absorbs RuleRecord and BankrollHero, which were two
// cards saying the rule's record and the money's record in the same shape.
//
//   THE RULE, ON PAPER   MY MONEY          LINE VALUE
//   56.0%                $103.60           +0.61
//   14-11 · 25 picks     3-3 · 6 bets      points the market came toward us
//   plausibly 37–73%     1 against the verdict   39% of 31 lines moved our way
//
// Each column is: the number at display size, then its record, then the one
// qualifier that keeps it honest (the interval, the discipline count, the
// share). No captions: the labels say what the numbers are.

const pct = (v: number) => `${(100 * v).toFixed(0)}%`;
const signedUnits = (u: number) => `${u > 0 ? "+" : ""}${u.toFixed(2)}u`;

export default function ScoreboardBand({
  paper,
  bankroll,
  points,
  realBets,
  againstVerdict,
  linesMoved,
}: {
  /** The rule's paper record (every card-qualified game, one flat unit). */
  paper: Record3 | null;
  bankroll: Bankroll;
  points: BankrollPoint[];
  /** Real-money first-half bets logged (pending or graded). */
  realBets: number;
  /** Real-money bets placed against the verdict. */
  againstVerdict: number;
  /** Graded picks with a close, and the share whose line moved toward us. */
  linesMoved: { n: number; pctFavourable: number | null };
}) {
  const b = bankroll;
  const delta = b.currentUsd - b.startUsd;
  const flat = Math.abs(delta) < 0.005;
  const interval =
    paper && paper.hitLo !== null && paper.hitHi !== null
      ? `plausibly ${pct(paper.hitLo)}–${pct(paper.hitHi)}`
      : "nothing decided yet";

  return (
    <section aria-label="Scoreboard" className="bv-card mb-8 p-5">
      <div className="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-3">
        <div>
          <span className="bv-stat-label">The rule, on paper</span>
          {paper === null ? (
            <EmptyLine className="mt-2">
              Fills in as the card’s paper picks grade.
            </EmptyLine>
          ) : (
            <>
              <p className="mt-2 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
                {paper.hit}
              </p>
              <p className="mt-2.5 font-mono text-sm text-[var(--text-muted)]">
                {`${paper.record} · ${paper.n} picks · `}
                <span style={{ color: unitColor(paper.units) }}>
                  {`${paper.units}u`}
                </span>
              </p>
              <p className="mt-1 text-xs text-[var(--text-dim)]">{interval}</p>
            </>
          )}
        </div>

        <div>
          <span className="bv-stat-label">My money</span>
          <p className="mt-2 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
            {usd(b.currentUsd)}
          </p>
          <p className="mt-2.5 font-mono text-sm text-[var(--text-muted)]">
            {b.real ? (
              <>
                {`${b.real.record} · ${realBets} ${realBets === 1 ? "bet" : "bets"} · `}
                <span style={{ color: unitColor(signedUnits(b.realUnits)) }}>
                  {signedUnits(b.realUnits)}
                </span>
                {` · ROI ${b.real.roi}`}
              </>
            ) : flat ? (
              `started ${usd(b.startUsd)} · nothing settled yet`
            ) : (
              `started ${usd(b.startUsd)}`
            )}
          </p>
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            {realBets === 0
              ? "no real-money bets yet"
              : `${againstVerdict} against the verdict`}
          </p>
        </div>

        <div>
          <span className="bv-stat-label">Line value</span>
          <p className="mt-2 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
            {paper?.clv ?? "—"}
          </p>
          <p className="mt-2.5 text-sm text-[var(--text-muted)]">
            points the market came toward us
          </p>
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            {linesMoved.n === 0 || linesMoved.pctFavourable === null
              ? "no closes captured yet"
              : `${linesMoved.pctFavourable.toFixed(0)}% of ${linesMoved.n} lines moved our way`}
          </p>
        </div>
      </div>

      {points.length < 2 ? (
        <EmptyLine className="mt-5">
          {`The curve starts once a week is graded. One unit is ${usd(b.unitUsd)}.`}
        </EmptyLine>
      ) : (
        <div className="mt-6">
          <BankrollCurve points={points} startUsd={b.startUsd} />
        </div>
      )}
    </section>
  );
}
