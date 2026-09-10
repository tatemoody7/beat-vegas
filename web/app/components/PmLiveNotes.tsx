import type { BandRow, LiveNotes } from "@/lib/postmortem";
import { EV_FLOOR_PCT } from "@/lib/verdict";

// The live season's own read: how close each line has been, whether a good
// Hard Rock price meant a better result, and what happens when Hard Rock
// prices away from the market. Hard Rock's number is a REAL line, so this
// belongs with the real-close evidence, not with the estimated-line block.

export default function PmLiveNotes({
  liveSeason,
  ln,
  hrVsMarket,
  hrVsMarketClose,
}: {
  liveSeason: string;
  ln: LiveNotes;
  hrVsMarket: BandRow[];
  hrVsMarketClose: BandRow[];
}) {
  return (
    <>
      <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
        {`${liveSeason} so far`}
      </h3>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        {`${ln.nGraded} of ${ln.nItems} rated games graded, ${ln.nBets} bets. Counts, not rates, until a group has 30 games.`}
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="bv-card p-4">
          <h4 className="text-sm font-semibold text-[var(--text)]">
            How close the lines have been
          </h4>
          <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
            Average points each line missed the actual first half by. Lower is
            closer. Actual first-half share is how much of the full-game total
            the first half really was.
          </p>
          <dl className="space-y-1 text-sm">
            <div className="flex justify-between">
              <dt className="bv-stat-label">Our reference line</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {ln.derivedMae === null ? "—" : ln.derivedMae.toFixed(1)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="bv-stat-label">Hard Rock’s line</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {ln.hrMae === null ? "—" : ln.hrMae.toFixed(1)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="bv-stat-label">The market line</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {ln.marketMae === null ? "—" : ln.marketMae.toFixed(1)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="bv-stat-label">Actual first-half share</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {ln.share === null ? "—" : ln.share.toFixed(3)}
              </dd>
            </div>
          </dl>
        </div>
        <div className="bv-card p-4">
          <h4 className="text-sm font-semibold text-[var(--text)]">
            Results by price
          </h4>
          <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
            Whether a good Hard Rock price actually meant a better result.
          </p>
          {ln.priceReads.length === 0 ? (
            <p className="text-xs text-[var(--text-dim)]">
              No priced games graded yet.
            </p>
          ) : (
            <dl className="space-y-1 text-sm">
              {ln.priceReads.map((p) => (
                <div key={p.band} className="flex justify-between">
                  <dt className="bv-stat-label">
                    {p.band === "pos"
                      ? "Better than fair"
                      : p.band === "neg"
                        ? `More than ${EV_FLOOR_PCT}% worse than fair`
                        : "About fair"}
                  </dt>
                  <dd className="font-mono text-[var(--text-muted)]">
                    {`${p.under} of ${p.under + p.over}${p.push ? ` (+${p.push} push)` : ""} under`}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        <div className="bv-card p-4">
          <h4 className="text-sm font-semibold text-[var(--text)]">
            When Hard Rock is off the market
          </h4>
          <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
            The under at Hard Rock’s line vs the under at the market’s close,
            same games.
          </p>
          {hrVsMarket.length === 0 ? (
            <p className="text-xs text-[var(--text-dim)]">
              No graded Hard Rock numbers yet.
            </p>
          ) : (
            <dl className="space-y-1 text-sm">
              {hrVsMarket.map((r) => {
                const close = hrVsMarketClose.find(
                  (c) => c.bucket === r.bucket,
                );
                return (
                  <div key={r.bucket} className="flex justify-between">
                    <dt className="bv-stat-label">{r.bucket}</dt>
                    <dd className="font-mono text-[var(--text-muted)]">
                      {`${r.record} at Hard Rock · ${close?.record ?? "—"} at the close`}
                    </dd>
                  </div>
                );
              })}
            </dl>
          )}
        </div>
      </div>
    </>
  );
}
