import {
  cardAge,
  summarizeCard,
  type Card,
  type CardRow,
  type CardTier,
} from "@/lib/card";

// This week's bet card on the home board, between the bankroll strip and the
// filters. Server component: everything it draws comes out of summarizeCard
// (pure, tested). Cyan is the brand accent — the BET chip is filled cyan, EDGE
// outlined — and green/red never appear here (nothing on the card has settled).

const TIER_CHIP: Record<CardTier, string> = {
  BET: "border-transparent bg-[var(--accent-strong)] text-[#04121f]",
  EDGE: "border-[var(--accent-strong)] text-[var(--accent)]",
  PASS: "border-[var(--border)] text-[var(--text-dim)]",
};

const MAX_NOTES = 5;

function Row({ r }: { r: CardRow }) {
  return (
    <li className="border-t border-[var(--border-soft)] py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span
          className={`rounded-md border px-2 py-0.5 text-xs font-bold tracking-wide ${TIER_CHIP[r.tier]}`}
        >
          {r.tier}
        </span>
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
                ? `Logged automatically as a paper pick (gate: ${r.paperBlocker}) — one notional unit, kept apart from the real record.`
                : "Logged automatically as a paper pick — one notional unit, kept apart from the real record."
            }
          >
            paper logged
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
          {`kill: ${r.kill}`}
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
          {`This week’s card`}
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
    <section className="bv-card mb-4 p-4" aria-label="This week's card">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          {`This week’s card`}
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
