import { describe, expect, it } from "vitest";
import {
  EV_CAVEAT,
  FEED_NOTE,
  NOTHING_POTENTIAL,
  SHORTLIST_HEAD,
  evText,
  ordinal,
  scoringText,
  shortlistFrom,
  verdictText,
} from "./shortlist";

// The research shortlist on the site (website plan PR E): the frozen rows read
// back in rank order, estimates worded as estimates, research wording only.

const entry = (rank: number, game_id: number) =>
  JSON.stringify({
    rank,
    game_id,
    label: "Fair price",
    price: { status: "priced" },
  });

const row = (rank: number, game_id: number, newest: number | null = 30) => ({
  card_id: 30,
  slot: "thu_pm",
  published_at: "2026-10-15 20:18:34.886696",
  card_built: "2026-10-15T20:17:15.232935",
  pool_size: 50,
  publication_sha256: "abc",
  payload_json: entry(rank, game_id),
  newest_card: newest,
});

describe("shortlistFrom", () => {
  it("reads one publication in research-rank order with its times as UTC", () => {
    const s = shortlistFrom([row(2, 22), row(1, 11)])!;
    expect(s.entries.map((e) => e.rank)).toEqual([1, 2]);
    expect(s.publishedAt.toISOString()).toBe("2026-10-15T20:18:34.886Z");
    expect(s.cardBuilt!.toISOString()).toBe("2026-10-15T20:17:15.232Z");
    expect(s.pool).toBe(50);
    expect(s.newerCardMissing).toBe(false);
  });

  it("says when a newer scheduled card has no publication", () => {
    expect(shortlistFrom([row(1, 11, 31)])!.newerCardMissing).toBe(true);
  });

  it("is null without rows, so the Board renders unchanged", () => {
    expect(shortlistFrom([])).toBeNull();
  });
});

describe("the words", () => {
  it("never shows a bare EV: always estimated, with its rough range", () => {
    expect(
      evText({
        hr_line: 29.5,
        hr_under: 100,
        hr_over: -120,
        hr_quote_at: null,
        breakeven: 0.5,
        hr_hold: 0.045,
        status: "priced",
        ev_point: 0.018,
        range_low: 0.0,
        range_high: 0.039,
      }),
    ).toBe("estimated EV +1.8% (rough range 0.0% to +3.9%)");
    expect(
      evText({
        hr_line: 29.5,
        hr_under: 100,
        hr_over: null,
        hr_quote_at: null,
        breakeven: 0.5,
        hr_hold: null,
        status:
          "insufficient pricing data (2 reference books in the same sweep)",
      }),
    ).toBe("no estimate (incomplete pricing)");
  });

  it("names percentiles and scoring plainly", () => {
    expect([1, 2, 3, 11, 12, 13, 21, 42].map(ordinal)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "11th",
      "12th",
      "13th",
      "21st",
      "42nd",
    ]);
    expect(scoringText("less")).toBe("points to less scoring");
    expect(scoringText(null)).toBe("middle third");
    expect(verdictText("null")).toBe("not shown to beat the line");
  });

  it("uses research wording: no bet language, no proven edge", () => {
    for (const s of [SHORTLIST_HEAD, NOTHING_POTENTIAL, EV_CAVEAT, FEED_NOTE]) {
      expect(s).not.toMatch(/\bbet\b|bet one|proven edge|guarantee/i);
    }
    expect(EV_CAVEAT).toContain("an estimate, not proof of profit");
  });
});
