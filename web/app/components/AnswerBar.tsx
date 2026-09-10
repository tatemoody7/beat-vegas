import Link from "next/link";
import type { Answer } from "@/lib/answerBar";

// The first thing on the board, and the only thing above the games. One row:
// what is bettable right now, how many cap slots are gone, and when the next
// decision build lands. When nothing is bettable — which is most weeks — it
// names the best game and what it needs instead of just saying "no bets".

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

      {live ? (
        <ul className="mt-2 space-y-1">
          {bets.map((b) => (
            <li key={b.gameId} className="text-sm">
              <Link
                href={`/game/${b.gameId}`}
                className="text-[var(--accent)] hover:underline"
              >
                {b.matchup}
              </Link>
              <span className="ml-2 font-mono text-[var(--text-muted)]">
                {b.numbers}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        closest !== null && (
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            <span className="text-[var(--text-dim)]">Closest · </span>
            <Link
              href={`/game/${closest.gameId}`}
              className="text-[var(--accent)] hover:underline"
            >
              {closest.matchup}
            </Link>
            <span className="ml-2">{closest.action}</span>
          </p>
        )
      )}

      {nextBuild !== null && (
        <p className="mt-2 text-xs text-[var(--text-dim)]">
          {`Next build ${nextBuild}`}
        </p>
      )}
    </div>
  );
}
