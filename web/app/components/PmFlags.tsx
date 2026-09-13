import { labelOf, SEVERITY_TEXT } from "@/lib/labels";
import type { PmFlag } from "@/lib/postmortem";
import { EmptyLine } from "@/app/components/Section";

// "What to change": one line per statement the tables judge, tagged change /
// watch / holds up.
//
// The WATCH tier is collapsed (Tate 2026-09-13). It ran to seven cards of which
// six were the same sentence with a different column name -- "wins and losses
// differ on <feature> ... A hypothesis to test on real 2026 lines, not a rule"
// -- roughly 700px telling you, at length, about things that are explicitly not
// actionable. They are still here, one click away, and still in
// docs/POST_MORTEM.md in full.

function FlagList({ flags }: { flags: PmFlag[] }) {
  return (
    <ul className="space-y-2">
      {flags.map((f) => (
        <li key={f.code} className="bv-card flex items-start gap-3 p-3">
          <span className="bv-pill shrink-0">
            <span className="bv-pill-value">
              {labelOf(SEVERITY_TEXT, f.severity, "watch")}
            </span>
          </span>
          <p className="text-sm text-[var(--text-muted)]">{f.text}</p>
        </li>
      ))}
    </ul>
  );
}

export default function PmFlags({ flags }: { flags: PmFlag[] }) {
  if (flags.length === 0) {
    return <EmptyLine>Nothing flagged yet.</EmptyLine>;
  }
  const acted = flags.filter((f) => f.severity !== "watch");
  const watched = flags.filter((f) => f.severity === "watch");
  return (
    <>
      {acted.length > 0 ? (
        <FlagList flags={acted} />
      ) : (
        <EmptyLine>
          Nothing to act on — everything checked is holding.
        </EmptyLine>
      )}
      {watched.length > 0 && (
        <details className="mt-2">
          <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-[var(--text-dim)]">
            {`${watched.length} more being watched`}
            <span aria-hidden="true">▾</span>
          </summary>
          <p className="mb-2 mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
            Suggestive, not actionable: each is a difference between winners and
            losers that has not been tested against a real 2026 line yet.
          </p>
          <FlagList flags={watched} />
        </details>
      )}
    </>
  );
}
