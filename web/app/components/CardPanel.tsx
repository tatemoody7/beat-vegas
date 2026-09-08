import {
  cardAge,
  summarizeCard,
  type Card,
  type CardRow,
  type CardTier,
} from "@/lib/card";
import { BLOCKER_SHORT, labelOf, TIER_TEXT } from "@/lib/labels";

// This week's bet list on the home board. Server component: everything it
// draws comes out of summarizeCard (pure, tested). The tier chip carries the
// grade colour (bet green, watch amber, pass grey); nothing here has settled.

const TIER_CHIP: Record<CardTier, string> = {
  BET: "bv-badge bv-badge--solid bv-badge--good",
  EDGE: "bv-badge bv-badge--warn",
  PASS: "bv-badge bv-badge--push",
};

const MAX_NOTES = 5;

function Row({ r }: { r: CardRow }) {
  return (
    <li className="border-t border-[var(--border-soft)] py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={TIER_CHIP[r.tier]}>{TIER_TEXT[r.tier]}</span>
        {r.capRank !== null && (
          <span
            className="font-mono text-xs text-[var(--text-dim)]"
            title="Rank among this week's BETs by gap — the order the weekly cap fills."
          >
            {`#${r.capRank}`}
          </span>
        )}
        <span className="font-semibold text-[var(--text)]">{r.matchup}</span>
        <span className="text-xs text-[var(--text-dim)]">
          {r.kick ?? "kickoff TBD"}
        </span>
        <span className="font-mono text-xs text-[var(--text-muted)]">
          {r.line}
        </span>
        {r.paperLogged && (
          <span
            className="rounded-md border border-[var(--accent-strong)] px-1.5 text-xs text-[var(--accent)]"
            title={
              r.paperBlocker
                ? `Logged with no money on it — ${labelOf(BLOCKER_SHORT, r.paperBlocker, "an input failed")}.`
                : "Logged with no money on it."
            }
          >
            logged as paper
          </span>
        )}
        <a
          href={`#game-${r.gameId}`}
          className="bv-nav-link ml-auto text-xs"
          title="Jump to this game on the board below."
        >
          Show on board
        </a>
      </div>
      {r.action !== "" && (
        <p className="mt-1 text-[var(--text-muted)]">{r.action}</p>
      )}
      {r.tier === "BET" && !r.overCap && r.kill !== "" && (
        <p className="mt-0.5 font-mono text-xs text-[var(--text-dim)]">
          {`Stops being a bet ${r.kill}`}
        </p>
      )}
    </li>
  );
}

export default function CardPanel({
  card,
  now = new Date(),
}: {
  card: Card | null;
  now?: Date;
}) {
  if (card === null) {
    return (
      <div className="bv-card mb-4 p-4">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          {`This week’s bets`}
        </h2>
        <p className="mt-1 text-sm text-[var(--text-dim)]">
          {`A preview builds Friday evening; the final card lands Saturday between 8:05 and 8:45am ET off a fresh sweep of Hard Rock’s first-half lines.`}
        </p>
      </div>
    );
  }

  const s = summarizeCard(card);
  const age = cardAge(card.builtAt, now);
  const notes = s.notes.slice(0, MAX_NOTES);

  return (
    <section className="bv-card mb-4 p-4" aria-label="This week's bets">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          {`This week’s bets`}
        </h2>
        {age !== null && (
          <span className="text-xs text-[var(--text-dim)]">{age}</span>
        )}
      </div>

      <p className="mt-2 text-sm text-[var(--text)]">
        <span className="font-semibold">{s.headline}</span>
        {s.reason !== null && (
          <span className="text-[var(--text-muted)]">{` ${s.reason}`}</span>
        )}
      </p>

      {s.hasBets ? (
        <>
          <ul className="mt-2">
            {s.bets.map((r) => (
              <Row key={r.gameId} r={r} />
            ))}
          </ul>
          {s.overCap.length > 0 && (
            <>
              <p
                className="mt-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]"
                title="Every gate passed on these too; the weekly cap makes them paper only."
              >
                Over the weekly cap · paper only
              </p>
              <ul className="mt-1">
                {s.overCap.map((r) => (
                  <Row key={r.gameId} r={r} />
                ))}
              </ul>
            </>
          )}
        </>
      ) : (
        s.closest.length > 0 && (
          <>
            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
              Closest to a bet
            </p>
            <ul className="mt-1">
              {s.closest.map((r) => (
                <Row key={r.gameId} r={r} />
              ))}
            </ul>
          </>
        )
      )}

      {s.degraded.length > 0 && (
        <>
          <p
            className="mt-3 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]"
            title="A card input failed on this build (a build-wide one shows in the banner; a missing pace read holds just its game), so the gate behind these could not be trusted: paper only, no weekly-cap slot."
          >
            Held · an input failed · paper only
          </p>
          <ul className="mt-1">
            {s.degraded.map((r) => (
              <Row key={r.gameId} r={r} />
            ))}
          </ul>
        </>
      )}

      {notes.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 border-t border-[var(--border-soft)] pt-2 text-xs text-[var(--text-dim)]">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
