import { describe, expect, it } from "vitest";

import { injuryNote, toPreviewGame, type PreviewRow } from "@/lib/previewRow";

const row = (over: Partial<PreviewRow>): PreviewRow => ({
  game_id: 1,
  week: 7,
  qb_out: null,
  qb_out_detail: "",
  news_json: JSON.stringify({ home: [], away: [] }),
  injuries_json: JSON.stringify({ home: [], away: [], covered: false }),
  updated_at: "2026-10-16 20:36:40",
  home_team: "Michigan",
  away_team: "Penn State",
  ...over,
});

describe("injury coverage (2026-10-17 audit: the feed is a five-row teaser)", () => {
  it("an uncovered game says the report is not available, never 'none'", () => {
    const p = toPreviewGame(row({}));
    expect(p.injuriesCovered).toBe(false);
    expect(p.qbOut).toBe(false);
    expect(injuryNote(p)).toContain("not available for this game");
    expect(injuryNote(p)).toContain("Starting QB status unknown");
  });

  it("a covered game shows its rows as a partial list", () => {
    const p = toPreviewGame(
      row({
        injuries_json: JSON.stringify({
          home: ["WR A. Player — Out"],
          away: [],
          covered: true,
        }),
      }),
    );
    expect(p.injuriesCovered).toBe(true);
    expect(p.homeInjuries).toEqual(["WR A. Player — Out"]);
    expect(injuryNote(p)).toContain("Partial list");
    expect(injuryNote(p)).toContain("not confirmed");
  });

  it("a listed QB out is shown as out, with no 'not confirmed' tail", () => {
    const p = toPreviewGame(
      row({
        qb_out: true,
        qb_out_detail: "Michigan: QB X — Out",
        injuries_json: JSON.stringify({
          home: ["QB X — Out"],
          away: [],
          covered: true,
        }),
      }),
    );
    expect(p.qbOut).toBe(true);
    expect(injuryNote(p)).not.toContain("not confirmed");
  });

  it("a row from before the flag counts as covered only if it lists someone", () => {
    expect(
      toPreviewGame(
        row({ injuries_json: JSON.stringify({ home: [], away: [] }) }),
      ).injuriesCovered,
    ).toBe(false);
    expect(
      toPreviewGame(
        row({
          injuries_json: JSON.stringify({ home: ["RB Y — Out"], away: [] }),
        }),
      ).injuriesCovered,
    ).toBe(true);
    expect(toPreviewGame(row({ injuries_json: null })).injuriesCovered).toBe(
      false,
    );
  });
});
