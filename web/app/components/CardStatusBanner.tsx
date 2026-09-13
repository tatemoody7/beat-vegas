import { cardHealth, type Card } from "@/lib/card";

// Sits on the BOARD, with the missed-build and stale-results banners (moved
// there from /results 2026-09-13 — it warns about the numbers you are about to
// bet off, so it belongs where you bet). Silent on a healthy card; otherwise
// one amber notice saying why the card should not be bet off as-is: a degraded
// input, a preview or manual build, or a card today's build has not replaced.
// Server component — everything comes out of cardHealth (pure, tested).
//
// `card` is nullable so the caller never has to guard: no card is not a
// warning about the card, and the board says "no card built yet" elsewhere.
export default function CardStatusBanner({
  card,
  now = new Date(),
}: {
  card: Card | null;
  now?: Date;
}) {
  if (card === null) return null;
  const health = cardHealth(card, now);
  if (health.level === "ok") return null;
  return (
    <div
      role="status"
      className="bv-card mb-4 border-l-2 border-[var(--warn)] p-4 text-sm text-[var(--text-muted)]"
    >
      <p className="font-medium text-[var(--text)]">{health.title}</p>
      {health.details.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5">
          {health.details.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
