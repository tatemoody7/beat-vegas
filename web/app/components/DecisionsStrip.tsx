import type { DecisionQuality } from "@/lib/decision-quality";

// "Your decisions" as one panel of six numbers in two columns, replacing two
// cards (Vs the closing line, Timing) that each carried a paragraph and a
// three-row list (Tate 2026-09-16: cards around numbers are boxes, not things).
// Every value is "figure (n)"; the label says what it is.

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;
const signed2 = (v: number | null | undefined, suffix = "") =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}${suffix}`;

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-[var(--border)] py-2 text-sm first:border-t-0">
      <dt className="text-[var(--text-muted)]">{label}</dt>
      <dd className="font-mono tabular-nums text-[var(--text)]">{value}</dd>
    </div>
  );
}

export default function DecisionsStrip({
  dq,
  realBets,
  againstVerdict,
}: {
  dq: DecisionQuality;
  realBets: number;
  againstVerdict: number;
}) {
  const c = dq.clv;
  const t = dq.timing;
  return (
    <div className="bv-table-wrap px-4 py-1">
      <dl className="grid grid-cols-1 gap-x-10 sm:grid-cols-2">
        <div>
          <Row
            label="Line value"
            value={`${signed2(c.avgPointsGained)} (${c.n})`}
          />
          <Row
            label="Lines that moved our way"
            value={`${pct(c.pctFavourable)} (${c.n})`}
          />
          <Row
            label="Price movement"
            value={`${signed2(c.avgPricePp, "pp")} (${c.nPrice})`}
          />
        </div>
        <div>
          <Row
            label="At or better than the open"
            value={`${pct(t.pctAtOrBetterThanOpen)} (${t.nOpen})`}
          />
          <Row
            label="Better than the close"
            value={`${pct(t.pctBeatingClose)} (${t.nClose})`}
          />
          <Row
            label="Real bets against the verdict"
            value={realBets === 0 ? "—" : `${againstVerdict} of ${realBets}`}
          />
        </div>
      </dl>
    </div>
  );
}
