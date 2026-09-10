import { labelOf, SEVERITY_TEXT } from "@/lib/labels";
import type { PmFlag } from "@/lib/postmortem";
import { EmptyLine } from "@/app/components/Section";

// "What to change": one line per statement the tables judge, tagged change /
// watch / holds up.

export default function PmFlags({ flags }: { flags: PmFlag[] }) {
  if (flags.length === 0) {
    return <EmptyLine>Nothing flagged yet.</EmptyLine>;
  }
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
