// Pure parsing of a game_previews row and the injury sentence the game page
// shows under it. No database import, so tests and any component can use it.

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
  /** The injury pull named at least one of this game's teams. Rotowire's public
   *  feed is capped at about five players from that day's games, so false is the
   *  normal case for a Saturday game: no injury read at all, not "none". Rows
   *  written before 2026-10-17 carry no flag; any listed injury counts. */
  injuriesCovered: boolean;
  updatedAt: string | null;
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

function coveredFlag(jsonStr: string | null): boolean {
  if (!jsonStr) return false;
  try {
    const o = JSON.parse(jsonStr);
    if (typeof o?.covered === "boolean") return o.covered;
  } catch {
    return false;
  }
  return arr(jsonStr, "home").length + arr(jsonStr, "away").length > 0;
}

export type PreviewRow = {
  game_id: number | bigint;
  week: number | bigint;
  qb_out: boolean | number | null;
  qb_out_detail: string | null;
  news_json: string | null;
  injuries_json: string | null;
  updated_at: string | null;
  home_team: string | null;
  away_team: string | null;
};

export function toPreviewGame(r: PreviewRow): PreviewGame {
  return {
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
    injuriesCovered: coveredFlag(r.injuries_json),
    updatedAt: r.updated_at,
  };
}

/** The plain sentence under a game's injury lists (2026-10-17 audit): the
 *  feed can show a QB is out but never that one is playing. */
export function injuryNote(p: PreviewGame): string {
  if (!p.injuriesCovered) {
    return "Injury report not available for this game: Rotowire's public feed lists only a few players, all from that day's games. Starting QB status unknown.";
  }
  return p.qbOut
    ? "Partial list: Rotowire's public feed shows only a few players."
    : "Partial list: Rotowire's public feed shows only a few players. Starting QB status not confirmed.";
}
