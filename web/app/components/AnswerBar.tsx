import Link from "next/link";
import type { Answer } from "@/lib/answerBar";

// The first thing on the board, and the only thing above the games. It answers
// both questions at once: what is bettable right now, and what is nearly there.
//
// It replaced three panels that each said "no bets this week" in different
// words before the first game appeared (the bankroll strip, the slip header and
// the card panel headline). Most weeks nothing is bettable, so the near-misses
// are what makes the block worth its space.

export default function AnswerBar({
  answer,
  nextBuild,
}: {
  answer: Answer;
  nextBuild: string | null;
}) {
  const { bets, open, closest, used, cap } = answer;
  const placed = bets.length - open;
  const live = open > 0;
  // What is left to decide leads. A week whose bets are all placed is not
  // "no bets yet", and a placed ticket is not "live" — it is done.
  const headline = live
    ? `${open} ${open === 1 ? "bet" : "bets"} live`
    : placed > 0
      ? `${placed} ${placed === 1 ? "bet" : "bets"} placed, nothing else live`
      : "No bets yet this week";

  return (
    <div
      className={`bv-card mb-4 p-4 ${live ? "bv-card--lit" : ""}`}
      aria-label="This week at a glance"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span
          className="text-lg font-semibold"
          style={{ color: live ? "var(--good)" : "var(--text)" }}
        >
          {headline}
        </span>
        <span className="font-mono text-sm text-[var(--text-muted)]">
          {`${used} of ${cap} slots used`}
        </span>
      </div>

      {bets.length > 0 && (
        <ul className="mt-2 space-y-1">
          {bets.map((b) => (
            <li
              key={b.gameId}
              className={`flex flex-wrap items-baseline gap-x-2 ${b.picked ? "opacity-60" : ""}`}
            >
              <Link
                href={`/game/${b.gameId}`}
                className={`text-sm font-semibold hover:underline ${b.picked ? "text-[var(--text-muted)]" : "text-[var(--accent)]"}`}
              >
                {b.matchup}
              </Link>
              <span
                className={`font-mono text-sm ${b.picked ? "text-[var(--text-muted)]" : "text-[var(--text)]"}`}
              >
                {b.numbers}
              </span>
              {b.picked && (
                <span className="bv-badge bv-badge--push">bet logged</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {closest.length > 0 && (
        <div className="mt-3 border-t border-[var(--border)] pt-2">
          <h2 className="mb-1.5 text-[0.6rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-dim)]">
            Closest to a bet
          </h2>
          <ul className="space-y-1.5">
            {closest.map((c) => (
              <li key={c.gameId}>
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <Link
                    href={`/game/${c.gameId}`}
                    className="text-sm text-[var(--accent)] hover:underline"
                  >
                    {c.matchup}
                  </Link>
                  <span className="font-mono text-xs text-[var(--text-muted)]">
                    {c.numbers}
                  </span>
                </div>
                <p className="text-xs text-[var(--warn)]">{c.needs}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {nextBuild !== null && (
        <p className="mt-3 text-xs text-[var(--text-dim)]">
          {`Next build ${nextBuild}`}
        </p>
      )}
    </div>
  );
}
