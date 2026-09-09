import { cardHealth, type Card } from "@/lib/card";

// Sits directly above the bet slip. Silent on a healthy card; otherwise one
// amber notice (the same shape as the board's no-model banner) saying why the
// card should not be bet off as-is: a degraded input, a preview or manual
// build, or a card this morning's build has not replaced yet. Server component —
// everything comes out of cardHealth (pure, tested).
export default function CardStatusBanner({
  card,
  now = new Date(),
}: {
  card: Card;
  now?: Date;
}) {
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
