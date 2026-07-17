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
      {/* Template literals, not JSX text nodes around {expr} — Next 16 dev has
          collapsed the space after an expression before ("2026season's"). */}
      {`No ${fallbackFrom} data yet — showing `}
      <span className="font-semibold text-[var(--text)]">{season}</span>
      {`. This view fills in once the ${fallbackFrom} season's first lines and predictions land.`}
    </p>
  );
}
