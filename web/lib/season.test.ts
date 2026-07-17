import { describe, expect, it } from "vitest";

import { currentCfbSeason, resolveSeason } from "./season";

const JUL_2026 = new Date(Date.UTC(2026, 6, 17));
const FEB_2026 = new Date(Date.UTC(2026, 1, 1));

describe("currentCfbSeason", () => {
  it("treats June+ as the upcoming season", () => {
    expect(currentCfbSeason(JUL_2026)).toBe(2026);
  });
  it("treats Jan-May as the season still wrapping up", () => {
    expect(currentCfbSeason(FEB_2026)).toBe(2025);
  });
});

describe("resolveSeason", () => {
  const seasons = [2025, 2024, 2023]; // no 2026 data yet

  it("honors an explicit valid selection with no fallback notice", () => {
    expect(resolveSeason(seasons, "2024", JUL_2026)).toEqual({
      season: 2024,
      fallbackFrom: null,
    });
  });

  it("flags the silent fallback to an older season", () => {
    expect(resolveSeason(seasons, undefined, JUL_2026)).toEqual({
      season: 2025,
      fallbackFrom: 2026,
    });
  });

  it("no notice once the current season has data", () => {
    expect(resolveSeason([2026, ...seasons], undefined, JUL_2026)).toEqual({
      season: 2026,
      fallbackFrom: null,
    });
  });

  it("ignores an invalid or unknown season param", () => {
    expect(resolveSeason(seasons, "1999", JUL_2026).season).toBe(2025);
    expect(resolveSeason(seasons, "banana", JUL_2026).season).toBe(2025);
  });

  it("falls back to the current season when no data exists at all", () => {
    expect(resolveSeason([], undefined, JUL_2026)).toEqual({
      season: 2026,
      fallbackFrom: null,
    });
  });
});
