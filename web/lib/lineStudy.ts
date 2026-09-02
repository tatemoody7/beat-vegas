import { unstable_cache } from "next/cache";
import { prisma } from "@/lib/prisma";
import { consensusLines } from "@/lib/board";
import { hasFbsSeason, isFbsGame, proxyTotal } from "@/lib/proxy";

// Port of beatvegas/analysis/line_study.py — for a season, how often the 1H
// under hit bucketed by the OPENING line (real pre-kickoff consensus open when
// snapshots exist, else the step-share proxy off the full-game total and
// spread). FBS-vs-FBS games only, min 15 games per bucket — the same defaults
// as the Python study so the two never disagree.

export const BREAKEVEN_PCT = 52.4; // under% needed to beat -110 juice
export const DEFAULT_MIN_GAMES = 15;

export type LineSource = "real_open" | "proxy";

export type LineBucket = {
  line: number;
  games: number;
  under: number;
  push: number;
  under_pct: number;
  line_source: LineSource;
};

export type StudyGame = {
  id: number;
  season: number;
  home: string | null;
  away: string | null;
  firstHalfTotal: number;
  fullGameTotal: number;
  spread: number | null;
};

export type TaggedGame = { fh: number; line: number; source: LineSource };

const roundHalf = (x: number) => Math.round(x * 2) / 2;

/** Pure: opening line per game — real consensus open when captured, else proxy. */
export function assignOpeningLine(
  games: StudyGame[],
  opens: Map<number, number>,
): TaggedGame[] {
  return games.map((g) => {
    const real = opens.get(g.id);
    return real !== undefined
      ? { fh: g.firstHalfTotal, line: roundHalf(real), source: "real_open" }
      : {
          fh: g.firstHalfTotal,
          line: proxyTotal(g.fullGameTotal, g.spread),
          source: "proxy",
        };
  });
}

/** Pure: bucket by opening line; drop buckets under minGames; rank by under%. */
export function bucketUnderRates(
  tagged: TaggedGame[],
  minGames = DEFAULT_MIN_GAMES,
): LineBucket[] {
  const groups = new Map<number, TaggedGame[]>();
  for (const t of tagged) {
    if (!groups.has(t.line)) groups.set(t.line, []);
    groups.get(t.line)!.push(t);
  }
  const buckets: LineBucket[] = [];
  for (const [line, rows] of groups) {
    const n = rows.length;
    if (n < minGames) continue;
    const under = rows.filter((r) => r.fh < r.line).length;
    const push = rows.filter((r) => r.fh === r.line).length;
    const decided = n - push;
    const under_pct =
      decided > 0 ? Math.round((1000 * under) / decided) / 10 : 0;
    const real = rows.filter((r) => r.source === "real_open").length;
    buckets.push({
      line,
      games: n,
      under,
      push,
      under_pct,
      line_source: real > n / 2 ? "real_open" : "proxy",
    });
  }
  buckets.sort((a, b) => b.under_pct - a.under_pct || a.line - b.line);
  return buckets;
}

type GameRow = {
  id: number | bigint;
  season: number | bigint;
  home_team: string | null;
  away_team: string | null;
  first_half_total: number | bigint;
  full_game_total: number;
  spread: number | null;
};

async function getLineStudyUncached(
  season: number,
  minGames = DEFAULT_MIN_GAMES,
): Promise<{ buckets: LineBucket[]; anyReal: boolean; fbsFiltered: boolean }> {
  const rows = await prisma.$queryRaw<GameRow[]>`
    SELECT id, season, home_team, away_team, first_half_total, full_game_total,
           spread
    FROM games
    WHERE season = ${season}
      AND first_half_total IS NOT NULL
      AND full_game_total > 0
  `;
  // FBS-vs-FBS only (etl/fbs.py). If the snapshot lacks this season we keep
  // every game and say so, rather than silently dropping the whole year.
  const fbsFiltered = hasFbsSeason(season);
  const games: StudyGame[] = rows
    .map((g) => ({
      id: Number(g.id),
      season: Number(g.season),
      home: g.home_team,
      away: g.away_team,
      firstHalfTotal: Number(g.first_half_total),
      fullGameTotal: Number(g.full_game_total),
      spread: g.spread === null ? null : Number(g.spread),
    }))
    .filter((g) => !fbsFiltered || isFbsGame(g.season, g.home, g.away));

  const consensus = await consensusLines(season);
  const opens = new Map<number, number>();
  for (const [gid, c] of consensus) if (c.open !== null) opens.set(gid, c.open);

  const buckets = bucketUnderRates(assignOpeningLine(games, opens), minGames);
  const anyReal = buckets.some((b) => b.line_source === "real_open");
  return { buckets, anyReal, fbsFiltered };
}

// History view — slow-changing, so cache the per-(season,minGames) computation.
export const getLineStudy = unstable_cache(
  getLineStudyUncached,
  ["line-study-v2"],
  { revalidate: 3600 },
);
