import { describe, expect, it } from "vitest";
import {
  BETS_CSV_HEADER,
  betsToCsv,
  groupByWeek,
  hoursBeforeKickoff,
  ledgerSummary,
  rowsFor,
  sortNewestFirst,
  withRunningUnits,
  type LedgerRow,
} from "./betLedger";

// A graded real-money winner on a -110 line, every field set, so a test can
// override the one thing it is about.
function row(over: Partial<LedgerRow> = {}): LedgerRow {
  return {
    id: 1,
    gameId: 900001,
    week: 3,
    away: "Stanford",
    home: "Duke",
    market: "1H",
    line: 26.5,
    price: -110,
    stake: 1,
    note: null,
    book: "hardrockbet",
    placedAt: "2026-09-18T20:12:00.000Z",
    kickoff: "2026-09-19T19:30:00.000Z",
    isPaper: false,
    isBonus: false,
    graded: true,
    result: "under",
    units: 0.91,
    awayFh: 7,
    homeFh: 10,
    actualTotal: 17,
    modelLine: 23.05,
    modelScore: 72,
    closingLine: 26.5,
    closingPrice: -112,
    closingCapturedAt: "2026-09-19T18:30:00.000Z",
    priceProvenance: "logged",
    clv: 0,
    clvProb: 0.01,
    verdictAtPick: "BET",
    reason: "model_gap",
    gapAtPick: 3.45,
    hrLineAtPick: 26.5,
    blocker: null,
    ...over,
  };
}

describe("sortNewestFirst", () => {
  it("orders by week, then posted time, then id, all descending", () => {
    const rows = [
      row({ id: 1, week: 2, placedAt: "2026-09-11T20:00:00.000Z" }),
      row({ id: 2, week: 3, placedAt: "2026-09-18T20:00:00.000Z" }),
      row({ id: 3, week: 3, placedAt: "2026-09-18T21:00:00.000Z" }),
      row({ id: 4, week: 3, placedAt: "2026-09-18T21:00:00.000Z" }),
      row({ id: 5, week: null, placedAt: null }),
    ];
    expect(sortNewestFirst(rows).map((r) => r.id)).toEqual([4, 3, 2, 1, 5]);
  });
});

describe("rowsFor", () => {
  it("splits the ledgers and keeps them apart", () => {
    const rows = [row({ id: 1 }), row({ id: 2, isPaper: true })];
    expect(rowsFor(rows, "real").map((r) => r.id)).toEqual([1]);
    expect(rowsFor(rows, "paper").map((r) => r.id)).toEqual([2]);
    expect(rowsFor(rows, "all").map((r) => r.id)).toEqual([1, 2]);
  });
});

describe("withRunningUnits", () => {
  it("accumulates oldest to newest and returns newest first", () => {
    const rows = [
      row({ id: 1, week: 2, units: 0.91 }),
      row({ id: 2, week: 2, units: -1, result: "over" }),
      row({ id: 3, week: 3, units: 0.87 }),
      row({ id: 4, week: 4, graded: false, result: "pending", units: null }),
    ];
    const out = withRunningUnits(rows);
    expect(out.map((r) => [r.id, r.runningUnits])).toEqual([
      [4, null],
      [3, 0.78],
      [2, -0.09],
      [1, 0.91],
    ]);
  });

  it("counts a bonus win like any other and a push adds nothing", () => {
    const rows = [
      row({ id: 1, week: 2, units: 1.54, isBonus: true }),
      row({ id: 2, week: 2, units: 0, result: "push" }),
    ];
    const out = withRunningUnits(rows);
    expect(out.find((r) => r.id === 2)?.runningUnits).toBe(1.54);
  });
});

describe("groupByWeek", () => {
  it("one group per week, newest first, each with its own record", () => {
    const rows = withRunningUnits([
      row({ id: 1, week: 2, units: 0.91 }),
      row({ id: 2, week: 2, units: -1, result: "over" }),
      row({ id: 3, week: 3, units: 0.87 }),
      row({ id: 4, week: 3, graded: false, result: "pending", units: null }),
    ]);
    const groups = groupByWeek(rows);
    expect(groups.map((g) => g.week)).toEqual([3, 2]);
    expect(groups[0].record?.record).toBe("1-0");
    expect(groups[0].pending).toBe(1);
    expect(groups[1].record?.record).toBe("1-1");
    expect(groups[1].record?.units).toBe("-0.09");
  });
});

describe("ledgerSummary", () => {
  it("records, counts pending bets, and reads line value in the displayed direction", () => {
    const s = ledgerSummary([
      row({ id: 1, clv: -1.0 }), // the line FELL: favourable
      row({ id: 2, clv: 0.5, result: "over", units: -1 }),
      row({ id: 3, clv: 0 }),
      row({ id: 4, graded: false, result: "pending", units: null, clv: null }),
    ]);
    expect(s.bets).toBe(4);
    expect(s.record?.record).toBe("2-1");
    expect(s.closes).toBe(3);
    expect(s.movedOurWay).toBe(1);
    // mean of -clv over the three closes: (1.0 - 0.5 + 0) / 3
    expect(s.record?.clv).toBe("+0.17");
  });

  it("a push is decided by nobody: out of the win rate, in the count", () => {
    const s = ledgerSummary([
      row({ id: 1 }),
      row({ id: 2, result: "push", units: 0 }),
    ]);
    expect(s.record?.record).toBe("1-0-1P");
    expect(s.record?.hit).toBe("100.0%");
  });
});

describe("hoursBeforeKickoff", () => {
  it("rounds to the hour and is null without both stamps", () => {
    expect(hoursBeforeKickoff(row())).toBe(23);
    expect(hoursBeforeKickoff(row({ kickoff: null }))).toBeNull();
    expect(
      hoursBeforeKickoff(row({ placedAt: "2026-09-19T21:30:00.000Z" })),
    ).toBe(-2);
    // Half an hour after kickoff rounds to zero, never to a negative zero.
    expect(
      Object.is(
        hoursBeforeKickoff(row({ placedAt: "2026-09-19T20:00:00.000Z" })),
        0,
      ),
    ).toBe(true);
  });
});

describe("betsToCsv", () => {
  it("writes the documented header, the stored clv beside its display, and quotes a note", () => {
    const csv = betsToCsv(2026, [
      row({ id: 1, clv: -1.0, note: 'slow pace, "both" defenses' }),
    ]);
    const lines = csv.trim().split("\n");
    expect(lines[0]).toBe(BETS_CSV_HEADER);
    expect(BETS_CSV_HEADER.split(",")).toHaveLength(30);
    const cells = lines[1];
    expect(
      cells.startsWith(
        "2026,3,2026-09-18T20:12:00.000Z,2026-09-19T19:30:00.000Z,real,Stanford,Duke,1H,under,26.5,-110,1,false,hardrockbet,logged,BET,model_gap,3.45,23.05,7,10,17,under,0.91,26.5,-112,-1,1,0.01,",
      ),
    ).toBe(true);
    expect(cells.endsWith('"slow pace, ""both"" defenses"')).toBe(true);
  });

  it("marks an ungraded row pending and a paper row paper", () => {
    const csv = betsToCsv(2026, [
      row({
        id: 2,
        isPaper: true,
        graded: false,
        result: "pending",
        units: null,
        clv: null,
      }),
    ]);
    const cells = csv.trim().split("\n")[1].split(",");
    expect(cells[4]).toBe("paper");
    expect(cells[22]).toBe("pending");
    expect(cells[27]).toBe("");
  });
});
