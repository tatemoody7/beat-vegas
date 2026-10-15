import Link from "next/link";
import { etClock12 } from "@/lib/et";
import { american, fmt } from "@/lib/format";
import {
  EV_CAVEAT,
  FEED_NOTE,
  LABEL_EXPENSIVE,
  LABEL_POTENTIAL,
  NOTHING_POTENTIAL,
  SHORTLIST_HEAD,
  evText,
  type Shortlist,
} from "@/lib/shortlist";

// The Research top 10 above the Board (Tate 2026-10-15, Q13): the frozen
// publication of the newest scheduled card, R1..R10, each row a link to the
// game page's full analysis. A research ranking, never the Board's rank and
// never a bet: the R prefix, the heading and the badge colours (no green)
// keep the two rankings apart. It renders nothing when there is no
// publication, so the Board never depends on it.

const LABEL_CLASS: Record<string, string> = {
  [LABEL_POTENTIAL]: "bv-badge--accent",
  [LABEL_EXPENSIVE]: "bv-badge--warn",
};

export default function ResearchTopTen({
  list,
  now = new Date(),
}: {
  list: Shortlist | null;
  now?: Date;
}) {
  if (list === null || list.entries.length === 0) return null;
  const anyPotential = list.entries.some((e) => e.label === LABEL_POTENTIAL);
  return (
    <section aria-label="Research top 10" className="mb-6">
      <h2 className="bv-day-head">{SHORTLIST_HEAD}</h2>
      <p className="mb-2 text-xs text-[var(--text-dim)]">
        {`From the ${list.cardBuilt ? etClock12(list.cardBuilt) : "latest"} build, published ${etClock12(list.publishedAt)} · ${list.pool} games considered · frozen, never re-ranked.`}
      </p>
      {list.newerCardMissing && (
        <p
          role="note"
          className="mb-2 border-l-2 border-[var(--warn)] pl-2 text-xs text-[var(--text-muted)]"
        >
          A newer build&apos;s shortlist did not publish; this is the earlier
          one.
        </p>
      )}
      {!anyPotential && (
        <p className="mb-2 text-sm text-[var(--text-muted)]">
          {NOTHING_POTENTIAL}
        </p>
      )}
      <ol className="flex flex-col gap-1.5">
        {list.entries.map((e) => {
          const kick = new Date(e.kick);
          const started = kick.getTime() <= now.getTime();
          return (
            <li key={e.game_id}>
              <Link
                href={`/game/${e.game_id}`}
                data-research-rank={e.rank}
                className={`flex min-h-11 flex-wrap items-center gap-x-3 gap-y-1 rounded-[var(--r-sm)] border border-[var(--border)] px-3 py-2 text-sm hover:border-[var(--accent)] ${started ? "opacity-70" : ""}`}
              >
                <span className="w-9 shrink-0 font-mono font-semibold text-[var(--accent)]">
                  {`R${e.rank}`}
                </span>
                <span className="min-w-0 flex-1 font-medium text-[var(--text)]">
                  {e.matchup}
                  <span className="ml-2 text-xs font-normal text-[var(--text-dim)]">
                    {started ? "kicked off" : etClock12(kick, ["a", "p"])}
                  </span>
                </span>
                <span className="font-mono text-xs text-[var(--text-muted)]">
                  {`u${fmt(e.price.hr_line)} ${american(e.price.hr_under)}`}
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  {evText(e.price)}
                </span>
                <span
                  className={`bv-badge ${LABEL_CLASS[e.label] ?? "bv-badge--push"}`}
                >
                  {e.label}
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        {`${EV_CAVEAT} ${FEED_NOTE}`}
      </p>
    </section>
  );
}
