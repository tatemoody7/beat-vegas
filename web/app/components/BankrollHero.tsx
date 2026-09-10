import { unitColor, usd } from "@/lib/format";
import type { Bankroll, BankrollPoint } from "@/lib/homeBoard";
import BankrollCurve from "@/app/components/BankrollCurve";
import { EmptyLine } from "@/app/components/Section";

// The money answer, at the top of the money page: what the bankroll is now,
// against what it started at, with the curve underneath.
//
// Everything here derives from the `Bankroll` the slip already loaded — no
// second query, no second season resolution. BankrollStrip used to carry
// these three numbers as small stats among five; it kept the cap state and
// the rules and gave these up, so nothing is said twice (Tate 2026-09-10).

const signedUnits = (u: number) => `${u > 0 ? "+" : ""}${u.toFixed(2)}u`;

export default function BankrollHero({
  b,
  points,
}: {
  b: Bankroll;
  points: BankrollPoint[];
}) {
  const delta = b.currentUsd - b.startUsd;
  const flat = Math.abs(delta) < 0.005;
  // Nothing settled is not a win. `unitColor` reads a flat "0.00" as good,
  // which is right in a ledger row and wrong at 3xl above an empty season.
  const unitsColor = b.real
    ? unitColor(signedUnits(b.realUnits))
    : "var(--text-dim)";
  return (
    <section aria-label="Bankroll" className="bv-card mb-6 p-5">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <span className="bv-stat-label">Bankroll</span>
          <p className="mt-1 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
            {usd(b.currentUsd)}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            {flat ? (
              `started ${usd(b.startUsd)} · nothing settled yet`
            ) : (
              <>
                {`started ${usd(b.startUsd)} · `}
                <span style={{ color: unitColor(signedUnits(delta)) }}>
                  {`${delta > 0 ? "+" : "-"}${usd(Math.abs(delta))}`}
                </span>
              </>
            )}
          </p>
        </div>
        <div>
          <span className="bv-stat-label">Units</span>
          <p
            className="mt-1 font-mono text-3xl font-semibold leading-none tabular-nums"
            style={{ color: unitsColor }}
          >
            {signedUnits(b.realUnits)}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            {b.real
              ? `${b.real.record} · ${b.real.hit} under`
              : "no settled bets"}
          </p>
        </div>
        <div>
          <span className="bv-stat-label">ROI</span>
          <p className="mt-1 font-mono text-3xl font-semibold leading-none tabular-nums text-[var(--text-muted)]">
            {b.real ? b.real.roi : "—"}
          </p>
          <p className="mt-1.5 text-xs text-[var(--text-dim)]">
            units won ÷ units risked
          </p>
        </div>
      </div>

      {points.length < 2 ? (
        <EmptyLine className="mt-4">
          {`The curve starts once a week is graded. One unit is ${usd(b.unitUsd)}, every bet.`}
        </EmptyLine>
      ) : (
        <div className="mt-5">
          <BankrollCurve points={points} startUsd={b.startUsd} />
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            {`Settled real-money bets only, at ${usd(b.unitUsd)} a unit. The dashed line is the ${usd(b.startUsd)} you started with. Pending bets do not move it.`}
          </p>
        </div>
      )}
    </section>
  );
}
