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
  const { bets, closest, used, cap } = answer;
  const live = bets.length > 0;

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
          {live
            ? `${bets.length} ${bets.length === 1 ? "bet" : "bets"} live`
            : "No bets yet this week"}
        </span>
        <span className="font-mono text-sm text-[var(--text-muted)]">
          {`${used} of ${cap} slots used`}
        </span>
      </div>

      {live && (
        <ul className="mt-2 space-y-1">
          {bets.map((b) => (
            <li
              key={b.gameId}
              className="flex flex-wrap items-baseline gap-x-2"
            >
              <Link
                href={`/game/${b.gameId}`}
                className="text-sm font-semibold text-[var(--accent)] hover:underline"
              >
                {b.matchup}
              </Link>
              <span className="font-mono text-sm text-[var(--text)]">
                {b.numbers}
              </span>
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
