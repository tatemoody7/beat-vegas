import type { PricingOpportunity } from "@/lib/armPicks";

// The pricing study's forward opportunities (2026-10-14, programme step 13):
// the rows the Monday report prints, carried in the stored H-PRICE-HR row so
// the site recomputes nothing. A flag below tier 2 is unverified for Florida
// (the feed has no Florida key); the study reads a direction only from 40.

const pct = (v: number | null) =>
  v === null ? "—" : `${v >= 0 ? "+" : ""}${(100 * v).toFixed(1)}%`;

const TIER: Record<number, string> = {
  0: "one feed observation",
  1: "quoted and re-seen",
  2: "seen in the Florida app",
  3: "ticket",
};

export default function PricingOpportunities({
  rows,
}: {
  rows: PricingOpportunity[];
}) {
  return (
    <section
      aria-label="Hard Rock pricing, forward opportunities"
      className="mt-10"
    >
      <h2 className="mb-1 text-lg font-semibold text-[var(--text)]">
        Hard Rock pricing, forward opportunities
      </h2>
      <p className="mb-3 max-w-[68ch] text-sm leading-relaxed text-[var(--text-muted)]">
        Every time since the rule was frozen (2026-10-13) that Hard Rock’s price
        sat at least 2% better than the market’s fair price for the same wager,
        from the Monday report. Unless seen in the Florida app, a flag is
        unverified for Florida.
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--text-dim)]">
          None yet. The study reads a direction only after 40.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table
            className="bv-table bv-table--dense"
            aria-label="Hard Rock pricing opportunities"
          >
            <thead>
              <tr>
                <th>Market</th>
                <th>Game</th>
                <th className="bv-num">Hard Rock</th>
                <th className="bv-num">Market</th>
                <th className="bv-num">Pick</th>
                <th className="bv-num">Value (lower bound)</th>
                <th className="bv-num">Value vs close</th>
                <th>Market moved</th>
                <th>Evidence</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((o, i) => (
                <tr key={`${o.game}-${o.market}-${i}`} className="align-top">
                  <td className="text-[var(--text-muted)]">{o.market}</td>
                  <td className="text-[var(--text)]">{o.game}</td>
                  <td className="bv-num font-mono">{o.hr_line ?? "—"}</td>
                  <td className="bv-num font-mono">{o.ref_line ?? "—"}</td>
                  <td className="bv-num whitespace-nowrap font-mono">{`${o.side} ${o.price ?? ""}`}</td>
                  <td className="bv-num font-mono">{pct(o.ev_ref_lower)}</td>
                  <td className="bv-num font-mono">{pct(o.ev_close)}</td>
                  <td className="text-[var(--text-muted)]">
                    {o.market_moved ?? "—"}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {TIER[o.tier ?? 0] ?? "—"}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {o.result ?? "pending"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
