import { labelOf, SEVERITY_TEXT } from "@/lib/labels";
import type { PmFlag } from "@/lib/postmortem";
import { EmptyLine } from "@/app/components/Section";

// "What to change": one line per statement the tables judge, tagged change /
// watch / holds up. Rows with a hairline between them, not a card each: a
// sentence is a note, not a thing (Tate 2026-09-16).
//
// The WATCH tier is collapsed (Tate 2026-09-13). It ran to seven cards of which
// six were the same sentence with a different column name; they are still
// here, one click away, and in docs/POST_MORTEM.md in full.

const PILL: Record<string, string> = {
  change: "border-[var(--warn-border)] text-[var(--warn)]",
  watch: "border-[var(--border)] text-[var(--text-dim)]",
};

function FlagList({ flags }: { flags: PmFlag[] }) {
  return (
    <ul className="border-b border-[var(--border)]">
      {flags.map((f) => (
        <li
          key={f.code}
          className="flex items-start gap-3 border-t border-[var(--border)] py-2.5"
        >
          <span
            className={`bv-pill mt-0.5 shrink-0 bg-transparent ${PILL[f.severity] ?? "border-[var(--border)] text-[var(--text-muted)]"}`}
          >
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
          <summary className="flex min-h-11 cursor-pointer items-center gap-2 text-sm text-[var(--accent)]">
            {`${watched.length} more being watched`}
            <span aria-hidden="true" className="text-[var(--text-dim)]">
              ▾
            </span>
          </summary>
          <FlagList flags={watched} />
        </details>
      )}
    </>
  );
}
