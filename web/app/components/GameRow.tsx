import Link from "next/link";
import { american, capitalize, fmt } from "@/lib/format";
import type { HomeGame } from "@/lib/homeBoard";
import { WEEKLY_BET_CAP } from "@/lib/verdict";
import ScoreBadge from "@/app/components/ScoreBadge";
import TeamLogo from "@/app/components/TeamLogo";

// One game on the board: rank badge, matchup, kickoff, Hard Rock's number and
// price, and one line saying what to do. Nothing else.
//
// It is a LINK, not a disclosure. The whole row navigates to /game/[id], where
// the gap bar, the book table, the movement chart and the factors live. The old
// card expanded to 1,790px in place, which is why one week ran to 11,600px.
//
// The badge is rank plus colour with no tier word: "Watch" was true of 35 of 49
// games, so it discriminated nothing, and the action line already says what to
// do. A live BET row is lit green — lit means act.
//
// Only the two chips that change whether you should bet survive here (a bet
// already logged, and being past the weekly cap). Early season and the blocker
// tag are on the game page; kicked off is already the badge reading LIVE.

export default function GameRow({ g }: { g: HomeGame }) {
  const { row, edge, check } = g;
  const hr =
    check?.hrLine == null
      ? "no line yet"
      : `u${fmt(check.hrLine)}${check.hrUnderPrice == null ? "" : ` ${american(check.hrUnderPrice)}`}`;
  const played = row.firstHalfTotal !== null;
  const resultLine =
    played && g.settled !== null
      ? `${capitalize(g.settled)} · first half ${fmt(row.firstHalfTotal, 0)}, line ${fmt(g.settledLine)}`
      : played
        ? `Final · first half ${fmt(row.firstHalfTotal, 0)}. No first-half line was posted, so nothing to grade.`
        : null;
  const lit = edge.tier === "BET" && !g.kickedOff;

  return (
    <Link
      id={`game-${row.gameId}`}
      href={`/game/${row.gameId}`}
      className={`bv-card scroll-mt-4 block p-4 ${lit ? "bv-card--lit" : ""} ${
        edge.tier === "PASS" && g.settled === null ? "opacity-85" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <ScoreBadge
          score={edge.score}
          rank={g.boardRank}
          kickedOff={g.kickedOff}
          inPlay={g.inPlay}
          settled={g.settled}
          label={null}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-base font-semibold leading-snug text-[var(--text)]">
              <TeamLogo teamId={row.awayTeamId} />
              {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
              <TeamLogo teamId={row.homeTeamId} />
              {row.home}
            </span>
            <span className="text-xs text-[var(--text-dim)]">
              {g.kickoff ?? "kickoff time TBD"}
            </span>
          </div>

          {(g.picked || g.overCap) && (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {g.picked && (
                <span className="bv-badge bv-badge--accent">bet logged</span>
              )}
              {g.overCap && (
                <span className="bv-badge bv-badge--push">{`past the ${WEEKLY_BET_CAP}-bet cap · paper only`}</span>
              )}
            </div>
          )}

          <div className="mt-1.5 font-mono text-xs text-[var(--text-muted)]">
            {hr}
          </div>

          <p
            className={`mt-1.5 text-sm ${
              played && g.settled === null
                ? "text-[var(--text-dim)]"
                : "text-[var(--text)]"
            }`}
          >
            {resultLine ?? edge.action}
          </p>
        </div>

        <span
          aria-hidden
          className="shrink-0 pt-1 text-xs text-[var(--text-dim)]"
        >
          →
        </span>
      </div>
    </Link>
  );
}
