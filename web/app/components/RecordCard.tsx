import { unitColor } from "@/lib/format";
import type { Record3 } from "@/lib/record";

// One record card for the whole site. Results and the track record used to
// carry near-identical private copies of this; they drifted only in whether
// line value was shown.
//
// `basis` is the honesty control. Everything on the track record graded
// against a line we WORKED OUT rather than one a book posted renders its units
// neutral, so green and red only ever appear on a real closing line (Tate
// 2026-09-10). Colour is the grade language, and an estimated grade is not a
// grade.
//
// Copy rule (spec §21-§23): `hint` is a visible line, never a `title=`.

export default function RecordCard({
  title,
  rec,
  hint,
  emptyHint,
  showClv = false,
  basis = "real",
}: {
  title: string;
  rec: Record3 | null;
  /** Visible line: what this record counts. */
  hint: string;
  /** Omit to render nothing at all when there is no record yet. */
  emptyHint?: string;
  showClv?: boolean;
  basis?: "real" | "estimated";
}) {
  if (rec === null && emptyHint === undefined) return null;
  const unitsColor =
    basis === "estimated" ? "var(--text-muted)" : unitColor(rec?.units);
  return (
    <div className="bv-card p-4">
      <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
      <p className="mb-2 mt-0.5 text-xs leading-relaxed text-[var(--text-dim)]">
        {hint}
      </p>
      {rec === null ? (
        <p className="text-xs text-[var(--text-dim)]">{emptyHint}</p>
      ) : (
        <dl className="space-y-3">
          <div>
            <dt className="bv-stat-label">Win rate</dt>
            <dd className="mt-0.5 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
              {rec.hit}
              <span className="ml-2 font-sans text-sm font-normal text-[var(--text-dim)]">
                {rec.record}
              </span>
            </dd>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            <div>
              <dt className="bv-stat-label">Units</dt>
              <dd
                className="mt-0.5 font-mono text-lg font-semibold tabular-nums"
                style={{ color: unitsColor }}
              >
                {rec.units}
              </dd>
            </div>
            <div>
              <dt className="bv-stat-label">ROI</dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                {rec.roi}
              </dd>
            </div>
            {showClv && (
              <div>
                <dt className="bv-stat-label">Line value</dt>
                <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                  {rec.clv}
                </dd>
              </div>
            )}
          </div>
        </dl>
      )}
    </div>
  );
}
