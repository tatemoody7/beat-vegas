import { etDateLabel } from "@/lib/et";
import type { ExploratoryCard as Card } from "@/lib/research";
import { PROTOCOL, pct } from "@/lib/research";

// An exploratory collector on the Research page (H-ARM-EVP, Tate's option A,
// 2026-10-14). Kept apart from the registered strategies: no progress bar
// toward a decision and no LLR, because there is no sequential test. It shows
// the judge's readings with the same "enough data" rule as the arms and, over
// exactly the same weeks, the gap rule's readings from the same stored row.

function evText(
  ev: { mean: number; lo: number | null; hi: number | null } | null,
  readings: number,
): string {
  if (ev === null)
    return readings === 0
      ? "nothing read yet"
      : `not enough data (${readings} of ${PROTOCOL.EV_INTERVAL_MIN_READINGS} to show one)`;
  return ev.lo === null || ev.hi === null
    ? `${pct(ev.mean)} (interval needs more)`
    : `${pct(ev.mean)} (${pct(ev.lo)} to ${pct(ev.hi)})`;
}

export default function ExploratoryCard({
  card,
  authed = false,
}: {
  card: Card;
  /** Signed in: the run id is the owner's detail (Q7). */
  authed?: boolean;
}) {
  const { meta } = card;
  return (
    <article
      aria-label={meta.name}
      data-hypothesis={meta.id}
      data-status={card.status}
      className="bv-card flex flex-col gap-2 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-[var(--text)]">
          {meta.name}
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <span className="bv-badge bv-badge--push">exploratory</span>
          <span className="bv-badge bv-badge--push" data-testid="status">
            {card.status}
          </span>
          {card.outdated && (
            <span className="bv-badge bv-badge--warn">outdated</span>
          )}
        </div>
      </div>
      <p className="text-sm leading-relaxed text-[var(--text-muted)]">
        {meta.rule}
      </p>
      <p className="font-mono text-xs text-[var(--text-muted)]">
        {`${card.readings} readings · ${card.weeks} week${card.weeks === 1 ? "" : "s"} · ${card.excluded} excluded`}
        {card.pending > 0 ? ` · ${card.pending} pending` : ""}
        {` · ${card.logged} logged`}
      </p>
      <p className="text-sm text-[var(--text)]">
        {`EV vs close: ${evText(card.ev, card.readings)}`}
      </p>
      {card.gap !== null && card.weeks > 0 && (
        <p
          className="text-sm text-[var(--text-muted)]"
          data-testid="comparison"
        >
          {`Same weeks, first-half unders by the gap: ${card.gap.readings} readings, EV vs close ${evText(card.gap.ev, card.gap.readings)}. Games both chose: ${card.both}; this rule only: ${card.evpOnly}; the gap only: ${card.gapOnly}.`}
        </p>
      )}
      <p className="text-xs text-[var(--text-dim)]">{meta.decides}</p>
      <p className="text-xs text-[var(--text-dim)]">
        {card.readAt === null
          ? "Not yet read."
          : `Last read ${etDateLabel(card.readAt)}${authed && card.runId && card.runId !== "-" ? ` · run ${card.runId}` : ""}`}
        {card.nextRead ? ` · Next read ${etDateLabel(card.nextRead)}` : ""}
      </p>
    </article>
  );
}
