// Shown when a view silently fell back to an older season because the current
// one has no data yet — stale must never be mistakable for live. Cyan accent
// (brand), never green/red (reserved for under/over outcomes).
export default function SeasonFallbackNotice({
  fallbackFrom,
  season,
}: {
  fallbackFrom: number | null;
  season: number;
}) {
  if (fallbackFrom === null) return null;
  return (
    <p className="bv-card mb-4 border-l-2 border-[var(--accent)] p-3 text-sm text-[var(--text-muted)]">
      No {fallbackFrom} data yet — showing{" "}
      <span className="font-semibold text-[var(--text)]">{season}</span>. This
      board fills in once the {fallbackFrom} season&apos;s first lines and
      predictions land.
    </p>
  );
}
