import Link from "next/link";
import type { ArmPick } from "@/lib/armPicks";
import { HYPOTHESES } from "@/lib/research";
import { american } from "@/lib/format";

// The registered arms' forward picks (2026-10-14, programme step 13): every
// graded paper pick since each arm's clock started, with the judge's reading
// or the reason there is none -- the rows the Monday read averages. A reading
// is a value at the pick's line and price against the vig-free close; an
// excluded pick counts and is never a reading. Development rows never appear.

const pct = (v: number) => `${v >= 0 ? "+" : ""}${(100 * v).toFixed(1)}%`;

const WHY: Record<string, string> = {
  far_lines: "the close sat too far from this line",
  few_books: "too few books at the close",
  stale_close: "no book closed inside 2 h of kickoff",
  outside_table: "line outside the conversion table",
  no_price: "no Hard Rock price was logged",
  no_hr_close: "no usable close",
};

export default function ArmPicksSection({
  picks,
}: {
  picks: Map<string, ArmPick[]>;
}) {
  const arms = HYPOTHESES.filter((h) => h.standard === "sprt");
  const total = arms.reduce((a, h) => a + (picks.get(h.id)?.length ?? 0), 0);
  return (
    <section aria-label="Paper strategies, forward picks" className="mt-10">
      <h2 className="mb-1 text-lg font-semibold text-[var(--text)]">
        Paper strategies, forward picks
      </h2>
      <p className="mb-3 max-w-[68ch] text-sm leading-relaxed text-[var(--text-muted)]">
        Every graded paper pick since each strategy’s clock started, with its
        value against the close or the reason it has none. These are the rows
        the Monday read averages; where each strategy stands is on{" "}
        <Link
          href="/research"
          className="inline-flex min-h-6 items-center text-[var(--accent)] hover:underline"
        >
          Research
        </Link>
        .
      </p>
      {total === 0 ? (
        <p className="text-sm text-[var(--text-dim)]">
          No forward pick has been graded yet.
        </p>
      ) : (
        arms.map((h) => {
          const rows = picks.get(h.id) ?? [];
          const read = rows.filter((r) => r.evCons !== null).length;
          return (
            <div key={h.id} data-arm={h.id} className="mb-4">
              <h3 className="bv-day-head">
                {`${h.name} · ${rows.length} graded · ${read} read · ${rows.length - read} excluded`}
              </h3>
              {rows.length > 0 && (
                <div className="bv-table-wrap">
                  <table
                    className="bv-table bv-table--dense"
                    aria-label={`${h.name} forward picks`}
                  >
                    <thead>
                      <tr>
                        <th>Week</th>
                        <th>Matchup</th>
                        <th className="bv-num">Pick</th>
                        <th>Result</th>
                        <th className="bv-num">Value vs close</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={`${r.arm}-${r.id}`} className="align-top">
                          <td className="text-[var(--text-muted)]">
                            {r.week ?? "—"}
                          </td>
                          <td className="text-[var(--text)]">{`${r.away ?? "?"} @ ${r.home ?? "?"}`}</td>
                          <td className="bv-num whitespace-nowrap font-mono">
                            {`${r.market === "full" ? "FG" : "1H"} ${r.side} ${r.line ?? "—"} ${r.price === null ? "" : american(r.price)}`}
                          </td>
                          <td className="text-[var(--text-muted)]">
                            {r.result ?? "—"}
                          </td>
                          <td className="bv-num font-mono">
                            {r.evCons !== null
                              ? pct(r.evCons)
                              : `excluded: ${WHY[r.consExcluded ?? ""] ?? r.consExcluded ?? "no reading"}`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })
      )}
    </section>
  );
}
