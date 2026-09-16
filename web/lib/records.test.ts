import { describe, expect, it } from "vitest";
import {
  defaultWeek,
  outcome,
  recordsToCsv,
  scoredAfter,
  type RecordRow,
} from "./records";

const row = (o: Partial<RecordRow> = {}): RecordRow => ({
  season: 2025,
  week: 3,
  away: "Kansas",
  home: "Missouri",
  fullGameTotal: 52.5,
  spread: -7,
  line: 27.5,
  bvLine: 25.1,
  bvGap: 2.4,
  bvGapZ: 0.2,
  underScore: 74,
  rank: 3,
  firstHalfTotal: 24,
  outcome: "under",

  scoredAfterKickoff: null,
  ...o,
});

describe("outcome", () => {
  it("grades the under against the line, with a push on the number", () => {
    expect(outcome(24, 27.5)).toBe("under");
    expect(outcome(31, 27.5)).toBe("over");
    expect(outcome(27, 27)).toBe("push");
  });
  it("is null when either side is missing", () => {
    // A played game with no captured line is not a loss — it is ungraded.
    expect(outcome(24, null)).toBeNull();
    expect(outcome(null, 27.5)).toBeNull();
  });
});

describe("recordsToCsv", () => {
  it("writes the header, one line per row, and a trailing newline", () => {
    const csv = recordsToCsv([row(), row({ week: 4 })]);
    const lines = csv.split("\n");
    expect(lines[0]).toBe(
      "season,week,away,home,full_game_total,spread,line_1h,bv_line,bv_gap,bv_gap_z,under_score,rank,first_half_total_actual,outcome,scored_after_kickoff",
    );
    expect(lines).toHaveLength(4); // header + 2 rows + trailing ""
    expect(lines[3]).toBe("");
    expect(lines[1].split(",")).toHaveLength(15);
  });

  it("leaves a missing value as an empty cell, never a literal null", () => {
    const csv = recordsToCsv([
      row({ line: null, bvLine: null, firstHalfTotal: null, outcome: null }),
    ]);
    expect(csv).not.toContain("null");
    expect(csv.split("\n")[1]).toBe(
      "2025,3,Kansas,Missouri,52.5,-7,,,2.4,0.2,74,3,,,",
    );
  });

  it("quotes a team name containing a comma so the columns do not shift", () => {
    const csv = recordsToCsv([row({ home: "Texas A&M, College Station" })]);
    const body = csv.split("\n")[1];
    expect(body).toContain('"Texas A&M, College Station"');
    // Still 15 fields once the quoted comma is respected.
    expect(body.match(/"/g)).toHaveLength(2);
  });

  it("is the header plus a blank line when there are no rows", () => {
    // The join of zero rows is "", so an empty season downloads a header and
    // one empty line. Harmless in every spreadsheet we have opened it in;
    // pinned so it is a known shape rather than a surprise.
    expect(recordsToCsv([])).toBe(
      "season,week,away,home,full_game_total,spread,line_1h,bv_line,bv_gap,bv_gap_z,under_score,rank,first_half_total_actual,outcome,scored_after_kickoff\n\n",
    );
  });
});

describe("scoredAfter", () => {
  it("is true only when the prediction postdates kickoff, null when unknown", () => {
    expect(scoredAfter("2026-09-10T21:45:05Z", "2026-08-29T23:00:00Z")).toBe(
      true,
    );
    expect(scoredAfter("2026-09-08T20:34:57Z", "2026-09-12T16:00:00Z")).toBe(
      false,
    );
    expect(scoredAfter(null, "2026-09-12T16:00:00Z")).toBeNull();
    expect(scoredAfter("2026-09-08T20:34:57Z", null)).toBeNull();
  });
});

describe("defaultWeek", () => {
  it("opens on the latest week with a graded game, not the last week scheduled", () => {
    const rows = [
      { week: 1, outcome: "under" as const },
      { week: 2, outcome: "over" as const },
      { week: 3, outcome: null },
      { week: 15, outcome: null }, // Navy @ Army, on the schedule from day one
    ];
    expect(defaultWeek(rows)).toBe(2);
  });

  it("is null when nothing has been graded yet", () => {
    expect(defaultWeek([{ week: 1, outcome: null }])).toBeNull();
    expect(defaultWeek([])).toBeNull();
  });
});
