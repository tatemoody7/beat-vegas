import { describe, expect, it } from "vitest";
import {
  defaultWeek,
  kickoffMs,
  outcome,
  recordsToCsv,
  scoredAfter,
  trustedFirstHalf,
  underUnits,
  viewTotals,
  type RecordRow,
} from "./records";

const row = (o: Partial<RecordRow> = {}): RecordRow => ({
  season: 2025,
  week: 3,
  away: "Kansas",
  home: "Missouri",
  gameId: 1,
  fullGameTotal: 52.5,
  spread: -7,
  bvLine: 25.1,
  rank: 3,
  firstHalfTotal: 24,
  hrLine: 27.5,
  hrPrice: -110,
  hrGap: 2.4,
  hrOutcome: "under",
  hrUnits: 0.91,
  consLine: 27,
  consGap: 1.9,
  consOutcome: "under",
  scoredAfterKickoff: null,
  kickoffMs: null,
  ...o,
});

const HEADER =
  "season,week,away,home,full_game_total,spread,bv_line,rank,hr_line_last_card,hr_price_last_card,hr_gap,hr_result,hr_units,consensus_close,consensus_gap,consensus_result,first_half_total_actual,scored_after_kickoff";

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
    expect(lines[0]).toBe(HEADER);
    expect(lines).toHaveLength(4); // header + 2 rows + trailing ""
    expect(lines[3]).toBe("");
    expect(lines[1].split(",")).toHaveLength(18);
  });

  it("never carries the scoring-time line again (audit 2026-10-17)", () => {
    expect(HEADER).not.toMatch(/line_1h|bv_gap|,outcome,/);
  });

  it("leaves a missing value as an empty cell, never a literal null", () => {
    const csv = recordsToCsv([
      row({
        hrLine: null,
        hrPrice: null,
        hrGap: null,
        hrOutcome: null,
        hrUnits: null,
        bvLine: null,
        firstHalfTotal: null,
      }),
    ]);
    expect(csv).not.toContain("null");
    expect(csv.split("\n")[1]).toBe(
      "2025,3,Kansas,Missouri,52.5,-7,,3,,,,,,27,1.9,under,,",
    );
  });

  it("quotes a team name containing a comma so the columns do not shift", () => {
    const csv = recordsToCsv([row({ home: "Texas A&M, College Station" })]);
    const body = csv.split("\n")[1];
    expect(body).toContain('"Texas A&M, College Station"');
    expect(body.match(/"/g)).toHaveLength(2);
  });

  it("is the header plus a blank line when there are no rows", () => {
    expect(recordsToCsv([])).toBe(`${HEADER}\n\n`);
  });
});

describe("trustedFirstHalf", () => {
  it("trusts a 0-0 half only with its proof, as the grader does", () => {
    expect(trustedFirstHalf(0, 21, 14, "linescores")).toBeNull();
    expect(trustedFirstHalf(0, 21, 14, "linescores_verified")).toBe(0);
    expect(trustedFirstHalf(0, 21, 14, "pbp")).toBe(0);
    expect(trustedFirstHalf(0, 0, 0, "linescores")).toBe(0);
    expect(trustedFirstHalf(17, 21, 14, null)).toBe(17);
    expect(trustedFirstHalf(null, 21, 14, null)).toBeNull();
  });
});

describe("underUnits", () => {
  it("pays one unit at the American price, -1 on a loss, 0 on a push", () => {
    expect(underUnits("under", -110)).toBeCloseTo(0.9091, 4);
    expect(underUnits("under", 120)).toBe(1.2);
    expect(underUnits("over", -110)).toBe(-1);
    expect(underUnits("push", -110)).toBe(0);
    expect(underUnits(null, -110)).toBeNull();
    expect(underUnits("under", null)).toBeNull();
  });
});

describe("viewTotals", () => {
  const rows = [
    row({}),
    row({ hrOutcome: "over", hrUnits: -1, consOutcome: "over" }),
    row({ hrLine: null, hrPrice: null, hrOutcome: null, hrUnits: null }), // no verified HR line
    row({ consLine: null, consOutcome: null }), // no consensus close
    row({ firstHalfTotal: null, hrOutcome: null, consOutcome: null }), // unplayed
  ];
  it("grades Hard Rock Records at Hard Rock's price and counts the games without a line", () => {
    const t = viewTotals(rows, "hr");
    expect(t.graded).toBe(3);
    expect(t.missing).toBe(1);
    expect(t.record?.record).toBe("2-1");
    expect(t.record?.units).toBe("+0.82");
  });
  it("reads Market Research as a record only, never units", () => {
    const t = viewTotals(rows, "market");
    expect(t.graded).toBe(3);
    expect(t.missing).toBe(1);
    expect(t.record?.record).toBe("2-1");
    expect(t.record?.roi).toBe("—");
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
      { week: 1, firstHalfTotal: 21 },
      { week: 2, firstHalfTotal: 30 },
      { week: 3, firstHalfTotal: null },
      { week: 15, firstHalfTotal: null }, // Navy @ Army, on the schedule from day one
    ];
    expect(defaultWeek(rows)).toBe(2);
  });

  it("is null when nothing has been graded yet", () => {
    expect(defaultWeek([{ week: 1, firstHalfTotal: null }])).toBeNull();
    expect(defaultWeek([])).toBeNull();
  });
});

describe("kickoffMs", () => {
  it("reads a Date, a zoned string and a naive string as the same UTC instant", () => {
    const ms = Date.UTC(2026, 9, 10, 19, 30);
    expect(kickoffMs(new Date(ms))).toBe(ms);
    expect(kickoffMs("2026-10-10T19:30:00Z")).toBe(ms);
    expect(kickoffMs("2026-10-10 19:30:00")).toBe(ms);
  });
  it("is null when unknown or unparseable", () => {
    expect(kickoffMs(null)).toBeNull();
    expect(kickoffMs(undefined)).toBeNull();
    expect(kickoffMs("not a date")).toBeNull();
  });
  it("is not a CSV column", () => {
    const head = recordsToCsv([row({ kickoffMs: 1 })]).split("\n")[0];
    expect(head.split(",")).toHaveLength(18);
    expect(head.split(",").at(-1)).toBe("scored_after_kickoff");
    expect(head).not.toContain("game_id");
  });
});
