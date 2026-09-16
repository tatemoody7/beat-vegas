import { cache } from "react";
import { prisma } from "@/lib/prisma";

// Week research preview: this week's games + injuries/QB-out (Rotowire's college
// injury report) and team news (ESPN), pulled by scripts/research_preview.py
// into game_previews. DISPLAY ONLY — both sources are unofficial.

export type PreviewGame = {
  gameId: number;
  week: number;
  away: string | null;
  home: string | null;
  qbOut: boolean;
  qbOutDetail: string | null;
  homeNews: string[];
  awayNews: string[];
  homeInjuries: string[];
  awayInjuries: string[];
  updatedAt: string | null;
};

export type Preview = {
  week: number | null;
  weeks: number[];
  games: PreviewGame[];
};

function arr(jsonStr: string | null, key: "home" | "away"): string[] {
  if (!jsonStr) return [];
  try {
    const o = JSON.parse(jsonStr);
    return Array.isArray(o?.[key]) ? o[key] : [];
  } catch {
    return [];
  }
}

const EMPTY: Preview = { week: null, weeks: [], games: [] };

// game_previews is written by scripts/research_preview.py and is NOT in the
// Prisma schema; on a fresh database (or before the first Tuesday pull) the
// table may not exist. Degrade to "no preview" instead of a 500.
export async function getPreview(
  season: number,
  week?: number,
): Promise<Preview> {
  try {
    return await getPreviewUnsafe(season, week);
  } catch (e) {
    console.warn("game_previews unavailable:", (e as Error)?.message ?? e);
    return EMPTY;
  }
}

/** Previews for one week keyed by game id — for the This Week cards.
 *  cache()d per request: /game/[id] builds the board in generateMetadata AND
 *  the body, and this ~128 KB pull was not deduped like the loaders in
 *  lib/board.ts are. */
export const getPreviewByGame = cache(async function getPreviewByGame(
  season: number,
  week: number,
): Promise<Map<number, PreviewGame>> {
  const p = await getPreview(season, week);
  const out = new Map<number, PreviewGame>();
  if (p.week !== week) return out; // fell back to another week: no match
  for (const g of p.games) out.set(g.gameId, g);
  return out;
});

async function getPreviewUnsafe(
  season: number,
  week?: number,
): Promise<Preview> {
  const wkRows = await prisma.$queryRaw<{ week: number | bigint | null }[]>`
    SELECT DISTINCT week FROM game_previews WHERE season = ${season} ORDER BY week
  `;
  const weeks = wkRows
    .map((r) => Number(r.week))
    .filter((w) => Number.isFinite(w));
  // Default to the most recently-previewed (latest) week.
  const wk =
    week && weeks.includes(week) ? week : (weeks[weeks.length - 1] ?? null);
  if (wk === null) return { week: null, weeks, games: [] };

  const rows = await prisma.$queryRaw<
    {
      game_id: number | bigint;
      week: number | bigint;
      qb_out: boolean | number | null;
      qb_out_detail: string | null;
      news_json: string | null;
      injuries_json: string | null;
      updated_at: string | null;
      home_team: string | null;
      away_team: string | null;
    }[]
  >`
    SELECT p.game_id, p.week, p.qb_out, p.qb_out_detail, p.news_json,
           p.injuries_json, CAST(p.updated_at AS TEXT) AS updated_at,
           g.home_team, g.away_team
    FROM game_previews p JOIN games g ON g.id = p.game_id
    WHERE p.season = ${season} AND p.week = ${wk}
    ORDER BY g.start_date
  `;

  const games: PreviewGame[] = rows.map((r) => ({
    gameId: Number(r.game_id),
    week: Number(r.week),
    away: r.away_team,
    home: r.home_team,
    qbOut: r.qb_out === true || Number(r.qb_out) === 1,
    qbOutDetail: r.qb_out_detail,
    homeNews: arr(r.news_json, "home"),
    awayNews: arr(r.news_json, "away"),
    homeInjuries: arr(r.injuries_json, "home"),
    awayInjuries: arr(r.injuries_json, "away"),
    updatedAt: r.updated_at,
  }));

  return { week: wk, weeks, games };
}
