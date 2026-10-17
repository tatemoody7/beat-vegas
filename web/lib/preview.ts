import { cache } from "react";
import { prisma } from "@/lib/prisma";
import {
  toPreviewGame,
  type PreviewGame,
  type PreviewRow,
} from "@/lib/previewRow";

export type { PreviewGame } from "@/lib/previewRow";

// Week research preview: this week's games + injuries/QB-out (Rotowire's college
// injury report) and team news (ESPN), pulled by scripts/research_preview.py
// into game_previews. DISPLAY ONLY — both sources are unofficial.

export type Preview = {
  week: number | null;
  weeks: number[];
  games: PreviewGame[];
};

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

  const rows = await prisma.$queryRaw<PreviewRow[]>`
    SELECT p.game_id, p.week, p.qb_out, p.qb_out_detail, p.news_json,
           p.injuries_json, CAST(p.updated_at AS TEXT) AS updated_at,
           g.home_team, g.away_team
    FROM game_previews p JOIN games g ON g.id = p.game_id
    WHERE p.season = ${season} AND p.week = ${wk}
    ORDER BY g.start_date
  `;

  const games: PreviewGame[] = rows.map(toPreviewGame);

  return { week: wk, weeks, games };
}
