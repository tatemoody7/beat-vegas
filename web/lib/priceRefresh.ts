import { GITHUB_REF, GITHUB_REPO } from "@/lib/cronJobs";

// The site's "Refresh price" (M2, 2026-10-07). A real ticket needs a Hard Rock
// price SEEN in the last HR_PRICE_MAX_AGE_H hours (lib/ticketPolicy.ts); our
// snapshots land at the decision builds and the evening close polls, so a
// midweek log can find only a day-old one. Refresh dispatches ONE poll of ONE
// game (lines_watch.yml market=1h_game, scripts/poll_lines.py --game-id, 1
// Odds API credit) instead of porting the Odds API client to the web.
//
// It is a credit-spending button, so the route refuses everything it can
// before dispatching: an unknown or kicked-off game, a price that is already
// fresh, a low credit gauge, and a second request inside the cooldown. The
// cooldown lives in the database (app_settings), never in process memory:
// Vercel runs separate instances that share nothing.

/** One refresh per game per this many minutes, claimed atomically in SQL. */
export const REFRESH_COOLDOWN_MIN = 10;
/** No refresh below this many remaining credits (poll_lines --credit-floor). */
export const REFRESH_CREDIT_FLOOR = 300;
export const REFRESH_WORKFLOW = "lines_watch.yml";

/** app_settings key holding a game's last refresh request (String(32)). */
export const refreshKey = (gameId: number): string => `price_refresh_${gameId}`;

/** The body is reduced to one positive integer; anything else is refused. */
export function parseRefreshBody(
  body: unknown,
): { ok: true; gameId: number } | { ok: false; error: string } {
  if (!body || typeof body !== "object") {
    return { ok: false, error: "Could not read the request." };
  }
  const g = (body as Record<string, unknown>).gameId;
  const n = typeof g === "number" ? g : typeof g === "string" ? Number(g) : NaN;
  if (!Number.isInteger(n) || n <= 0 || n > 999_999_999_999) {
    return { ok: false, error: "Missing the game." };
  }
  return { ok: true, gameId: n };
}

/** The workflow_dispatch body: the game id is the only value passed through. */
export function refreshDispatchBody(gameId: number): {
  ref: string;
  inputs: { market: "1h_game"; game_id: string };
} {
  return {
    ref: GITHUB_REF,
    inputs: { market: "1h_game", game_id: String(gameId) },
  };
}

export const REFRESH_DISPATCH_URL = `https://api.github.com/repos/${GITHUB_REPO}/actions/workflows/${REFRESH_WORKFLOW}/dispatches`;
