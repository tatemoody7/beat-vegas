import { getGauges, opsWarnings } from "@/lib/boardHealth";

// The board is the only place Tate looks, so the board says when the system
// is about to stop: an API budget near zero, a close poll that has not fired.
// Silent when every gauge is healthy (beatvegas/ops.py writes them). Server
// component; the read never throws (getGauges returns empty on failure).
export default async function OpsBanner({ now = new Date() }: { now?: Date }) {
  const warnings = opsWarnings(await getGauges(), now);
  if (warnings.length === 0) return null;
  return (
    <div
      role="status"
      className="bv-card mb-4 border-l-2 border-[var(--warn)] p-4 text-sm text-[var(--text-muted)]"
    >
      <p className="font-medium text-[var(--text)]">
        {warnings.length === 1
          ? "One thing needs attention."
          : `${warnings.length} things need attention.`}
      </p>
      <ul className="mt-1 flex flex-col gap-0.5">
        {warnings.map((w) => (
          <li key={w.key}>{w.text}</li>
        ))}
      </ul>
    </div>
  );
}
