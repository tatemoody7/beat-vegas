import { describe, expect, it } from "vitest";
import {
  parseRefreshBody,
  REFRESH_COOLDOWN_MIN,
  REFRESH_CREDIT_FLOOR,
  REFRESH_DISPATCH_URL,
  refreshDispatchBody,
  refreshKey,
} from "./priceRefresh";

// Refresh price (M2, 2026-10-07) spends an Odds API credit, so the request is
// reduced to one game id and the dispatch carries nothing else.

describe("parseRefreshBody", () => {
  it("takes one positive integer game id", () => {
    expect(parseRefreshBody({ gameId: 401856824 })).toEqual({
      ok: true,
      gameId: 401856824,
    });
    expect(parseRefreshBody({ gameId: "401856824" })).toEqual({
      ok: true,
      gameId: 401856824,
    });
  });
  it("refuses anything that is not one", () => {
    for (const gameId of [0, -1, 1.5, "abc", null, undefined, "1;rm -rf"]) {
      expect(parseRefreshBody({ gameId }).ok).toBe(false);
    }
    expect(parseRefreshBody(null).ok).toBe(false);
  });
});

describe("the dispatch", () => {
  it("passes only the market and the game id to lines_watch.yml on main", () => {
    expect(refreshDispatchBody(7)).toEqual({
      ref: "main",
      inputs: { market: "1h_game", game_id: "7" },
    });
    expect(REFRESH_DISPATCH_URL).toMatch(
      /\/repos\/tatemoody7\/beat-vegas\/actions\/workflows\/lines_watch\.yml\/dispatches$/,
    );
  });
  it("keys the cooldown per game, within app_settings' 32-character key", () => {
    expect(refreshKey(401856824)).toBe("price_refresh_401856824");
    expect(refreshKey(999_999_999_999).length).toBeLessThanOrEqual(32);
  });
  it("cooldown and credit floor are the values in the plan", () => {
    expect(REFRESH_COOLDOWN_MIN).toBe(10);
    expect(REFRESH_CREDIT_FLOOR).toBe(300);
  });
});
