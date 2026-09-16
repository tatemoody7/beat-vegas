import type { BandRow, LiveNotes } from "@/lib/postmortem";
import { EV_FLOOR_PCT } from "@/lib/verdict";

// The live season's own read, as ONE panel of three columns: how close each
// line has been, whether a good Hard Rock price meant a better result, and
// what happens when Hard Rock prices away from the market. It was three cards,
// each with a paragraph (Tate 2026-09-16: cards around numbers are boxes, not
// things). Hard Rock's number is a REAL line, so this belongs with the
// real-close evidence, not with the estimated-line block.

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-[var(--border)] py-2 text-sm first:border-t-0">
      <dt className="text-[var(--text-muted)]">{label}</dt>
      <dd className="text-right font-mono tabular-nums text-[var(--text)]">
        {value}
      </dd>
    </div>
  );
}

function Head({ children }: { children: string }) {
  return <p className="bv-stat-label mb-1 mt-2">{children}</p>;
}

const mae = (v: number | null) => (v === null ? "—" : v.toFixed(1));

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
      <h3 className="mb-2 mt-8 text-sm font-semibold text-[var(--text)]">
        {`${liveSeason} so far`}
        <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
          {`${ln.nGraded} of ${ln.nItems} rated games graded · ${ln.nBets} bets · counts until a group reaches 30`}
        </span>
      </h3>
      <div className="bv-table-wrap px-4 pb-2">
        <dl className="grid grid-cols-1 gap-x-10 sm:grid-cols-3">
          <div>
            <Head>Average miss, points</Head>
            <Row label="Hard Rock’s line" value={mae(ln.hrMae)} />
            <Row label="The market line" value={mae(ln.marketMae)} />
            <Row label="Our reference line" value={mae(ln.derivedMae)} />
            <Row
              label="Actual first-half share"
              value={ln.share === null ? "—" : ln.share.toFixed(3)}
            />
          </div>
          <div>
            <Head>Under, by Hard Rock’s price</Head>
            {ln.priceReads.length === 0 ? (
              <p className="py-2 text-xs text-[var(--text-dim)]">
                No priced games graded yet.
              </p>
            ) : (
              ln.priceReads.map((p) => (
                <Row
                  key={p.band}
                  label={
                    p.band === "pos"
                      ? "Better than fair"
                      : p.band === "neg"
                        ? `${EV_FLOOR_PCT}%+ worse than fair`
                        : "About fair"
                  }
                  value={`${p.under} of ${p.under + p.over}${p.push ? ` +${p.push}P` : ""}`}
                />
              ))
            )}
          </div>
          <div>
            <Head>Under at Hard Rock · at the close</Head>
            {hrVsMarket.length === 0 ? (
              <p className="py-2 text-xs text-[var(--text-dim)]">
                No graded Hard Rock numbers yet.
              </p>
            ) : (
              hrVsMarket.map((r) => {
                const close = hrVsMarketClose.find(
                  (c) => c.bucket === r.bucket,
                );
                return (
                  <Row
                    key={r.bucket}
                    label={r.bucket}
                    value={`${r.record} · ${close?.record ?? "—"}`}
                  />
                );
              })
            )}
          </div>
        </dl>
      </div>
    </>
  );
}
