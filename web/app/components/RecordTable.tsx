import { unitColor } from "@/lib/format";
import type { Record3 } from "@/lib/record";

// Several records compared down one column each: win rate, record, units, ROI,
// line value, and optionally the interval. Replaces a grid of RecordCards —
// four cards holding the same five numbers were "too many boxes" and made the
// eye jump between cards to compare a column (Tate 2026-09-16).
//
// `basis` is the honesty control carried over from RecordCard: anything graded
// against a line we WORKED OUT renders its units neutral, so green and red only
// ever appear on a real closing line.

export type RecordTableRow = {
  key: string;
  label: string;
  /** One quiet qualifier under the label, e.g. "the baseline to beat". */
  note?: string;
  rec: Record3 | null;
  /** What to print across the row when `rec` is null. */
  empty?: string;
  /** Context rows (the full-game market) render in the dim text step. */
  dim?: boolean;
  /** Bold the label: the row the page is about. */
  lead?: boolean;
};

const pct = (v: number) => `${(100 * v).toFixed(0)}%`;

export default function RecordTable({
  rows,
  showClv = false,
  showInterval = false,
  basis = "real",
  ariaLabel,
}: {
  rows: RecordTableRow[];
  showClv?: boolean;
  /** A "Plausibly" column with the 95% Wilson interval on the win rate. */
  showInterval?: boolean;
  basis?: "real" | "estimated";
  ariaLabel: string;
}) {
  const cols = 4 + (showClv ? 1 : 0) + (showInterval ? 1 : 0);
  return (
    <div className="bv-table-wrap">
      <table className="bv-table" aria-label={ariaLabel}>
        <thead>
          <tr>
            <th></th>
            <th className="bv-num">Win rate</th>
            <th className="bv-num">Record</th>
            <th className="bv-num">Units</th>
            <th className="bv-num">ROI</th>
            {showClv && <th className="bv-num">Line value</th>}
            {showInterval && <th className="bv-num">Plausibly</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const tone = r.dim
              ? "text-[var(--text-dim)]"
              : "text-[var(--text-muted)]";
            return (
              <tr key={r.key}>
                <td
                  className={`whitespace-nowrap ${
                    r.dim ? "text-[var(--text-dim)]" : "text-[var(--text)]"
                  }`}
                >
                  <span className={r.lead ? "font-semibold" : ""}>
                    {r.label}
                  </span>
                  {r.note && (
                    <span className="block text-xs leading-tight text-[var(--text-dim)]">
                      {r.note}
                    </span>
                  )}
                </td>
                {r.rec === null ? (
                  <td colSpan={cols} className="text-xs text-[var(--text-dim)]">
                    {r.empty ?? "—"}
                  </td>
                ) : (
                  <>
                    <td
                      className={`bv-num font-mono ${r.dim ? "text-[var(--text-dim)]" : "font-semibold text-[var(--text)]"}`}
                    >
                      {r.rec.hit}
                    </td>
                    <td className={`bv-num font-mono ${tone}`}>
                      {r.rec.record}
                    </td>
                    <td
                      className="bv-num font-mono"
                      style={{
                        color:
                          basis === "estimated" || r.dim
                            ? "var(--text-dim)"
                            : unitColor(r.rec.units),
                      }}
                    >
                      {r.rec.units}
                    </td>
                    <td className={`bv-num font-mono ${tone}`}>{r.rec.roi}</td>
                    {showClv && (
                      <td className={`bv-num font-mono ${tone}`}>
                        {r.rec.clv}
                      </td>
                    )}
                    {showInterval && (
                      <td className="bv-num font-mono text-[var(--text-dim)]">
                        {r.rec.hitLo === null || r.rec.hitHi === null
                          ? "—"
                          : r.rec.decided < 30
                            ? "too few"
                            : `${pct(r.rec.hitLo)}–${pct(r.rec.hitHi)}`}
                      </td>
                    )}
                  </>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
