import { unitColor } from "@/lib/format";
import type { BandRow } from "@/lib/postmortem";

// Win rate by gap size. Rows under 30 games grey out — a band that thin says
// nothing, and a number you cannot read is better than one you misread.

export default function BandTable({
  title,
  rows,
  caption,
  basis = "real",
}: {
  title: string;
  rows: BandRow[];
  /** Optional one-liner; the column heads carry the rest. */
  caption?: string;
  /**
   * "estimated" drops the green/red on units. Colour is the grade language,
   * and a record graded against a line we worked out is not a grade (Tate
   * 2026-09-10).
   */
  basis?: "real" | "estimated";
}) {
  return (
    <>
      <h3 className="mb-1 mt-4 text-sm font-semibold text-[var(--text)]">
        {title}
      </h3>
      {caption && (
        <p className="mb-2 text-xs leading-relaxed text-[var(--text-dim)]">
          {caption}
        </p>
      )}
      <div className="bv-table-wrap">
        <table className="bv-table">
          <thead>
            <tr>
              <th>Gap</th>
              <th className="bv-num">Games</th>
              <th className="bv-num">W-L-P</th>
              <th className="bv-num">Under %</th>
              <th className="bv-num">Range</th>
              <th className="bv-num">Chance it beats break-even</th>
              <th className="bv-num">Units</th>
              <th className="bv-num">ROI</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-[var(--text-muted)]">
                  Nothing graded here yet.
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const dim = r.size === "small";
                const cls = dim
                  ? "text-[var(--text-dim)]"
                  : "text-[var(--text-muted)]";
                return (
                  <tr key={r.bucket}>
                    <td
                      className={`whitespace-nowrap ${
                        dim ? "text-[var(--text-dim)]" : "text-[var(--text)]"
                      }`}
                    >
                      {r.bucket}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>{r.n}</td>
                    <td className={`bv-num font-mono whitespace-nowrap ${cls}`}>
                      {r.record}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>
                      {dim ? "too few" : r.hit}
                    </td>
                    <td className={`bv-num font-mono whitespace-nowrap ${cls}`}>
                      {dim ? "—" : r.ci}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>
                      {dim ? "—" : r.pBeat}
                    </td>
                    <td
                      className="bv-num font-mono"
                      style={{
                        color: dim
                          ? "var(--text-dim)"
                          : basis === "estimated"
                            ? "var(--text-muted)"
                            : unitColor(r.units),
                      }}
                    >
                      {r.units}
                    </td>
                    <td className={`bv-num font-mono ${cls}`}>{r.roi}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
