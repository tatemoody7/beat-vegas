import { describe, expect, it } from "vitest";
import type { LedgerRow } from "./betLedger";
import type { HomeGame } from "./homeBoard";
import type { RecordRow } from "./records";
import { gateGame, gateLedger, gateRecords, kickoffPassed } from "./signalGate";

const NOW = new Date(Date.UTC(2026, 9, 10, 18, 0));
const BEFORE = Date.UTC(2026, 9, 10, 17, 0);
const AFTER = Date.UTC(2026, 9, 10, 19, 30);

describe("kickoffPassed", () => {
  it("compares epoch ms and ISO strings to now", () => {
    expect(kickoffPassed(BEFORE, NOW)).toBe(true);
    expect(kickoffPassed(AFTER, NOW)).toBe(false);
    expect(kickoffPassed(new Date(BEFORE).toISOString(), NOW)).toBe(true);
    expect(kickoffPassed(new Date(AFTER).toISOString(), NOW)).toBe(false);
  });
  it("reads a naive string as UTC, never local time", () => {
    expect(kickoffPassed("2026-10-10 17:59:00", NOW)).toBe(true);
    expect(kickoffPassed("2026-10-10T18:01:00", NOW)).toBe(false);
  });
  it("fails closed on an unknown or unparseable kickoff", () => {
    expect(kickoffPassed(null, NOW)).toBe(false);
    expect(kickoffPassed(undefined, NOW)).toBe(false);
    expect(kickoffPassed("soon", NOW)).toBe(false);
  });
});

const game = (kickedOff: boolean): HomeGame =>
  ({
    row: { bvLine: 24.1, factors: { factor_board: [{ key: "wind" }] } },
    edge: {
      score: 81,
      tier: "BET",
      blocker: null,
      action: "Paper signal: first-half under 27.5 at -110 on Hard Rock.",
      kill: { line: 26, price: -120, text: "kill" },
      gap: 3.4,
      lineBasis: "hr",
      verdict: {},
    },
    kickedOff,
    picked: true,
    gap: 3.4,
    boardRank: 1,
    capRank: 1,
    overCap: false,
  }) as unknown as HomeGame;

describe("gateGame", () => {
  it("shows a visitor the owner's board before kickoff, without his bet-logged chip (roadmap v1.7)", () => {
    const pre = game(false);
    const g = gateGame(pre, false);
    expect(g.edge.score).toBe(81);
    expect(g.edge.gap).toBe(3.4);
    expect(g.edge.kill).toEqual(pre.edge.kill);
    expect(g.edge.action).toBe(pre.edge.action);
    expect(g.gap).toBe(3.4);
    expect(g.boardRank).toBe(1);
    expect(g.capRank).toBe(1);
    expect(g.row.bvLine).toBe(24.1);
    expect(g.row.factors.factor_board).toEqual([{ key: "wind" }]);
    // His real ticket stays his until kickoff, as the ledger withholds it.
    expect(g.picked).toBe(false);
  });
  it("passes the owner's game through untouched; a kicked-off game keeps its chip", () => {
    const pre = game(false);
    expect(gateGame(pre, true)).toBe(pre);
    const post = game(true);
    expect(gateGame(post, false)).toEqual(post);
  });

  it("never shows a visitor bet wording, before or after kickoff (roadmap v1.4)", () => {
    const post = game(true);
    const bet = {
      ...post,
      edge: {
        ...post.edge,
        action: "Bet one unit: first-half under 24.5 at -110 on Hard Rock.",
      },
    };
    expect(gateGame(bet, false).edge.action).toBe(
      "Paper signal: first-half under 24.5 at -110 on Hard Rock.",
    );
    expect(gateGame(bet, true).edge.action).toBe(bet.edge.action);
    expect(gateGame({ ...bet, kickedOff: false }, false).edge.action).toBe(
      "Paper signal: first-half under 24.5 at -110 on Hard Rock.",
    );
  });
});

describe("gateRecords", () => {
  const rec = (kickoffMs: number | null) =>
    ({
      bvLine: 24,
      bvGap: 3,
      bvGapZ: 0.4,
      rank: 2,
      line: 27,
      kickoffMs,
    }) as unknown as RecordRow;
  it("blanks our number, gap, z and rank before kickoff for a visitor", () => {
    const out = gateRecords([rec(AFTER), rec(null), rec(BEFORE)], false, NOW);
    expect(out).toHaveLength(3);
    for (const r of out.filter((x) => x.kickoffMs !== BEFORE)) {
      expect([r.bvLine, r.bvGap, r.bvGapZ, r.rank]).toEqual([
        null,
        null,
        null,
        null,
      ]);
      expect(r.line).toBe(27);
    }
    expect(out.find((x) => x.kickoffMs === BEFORE)!.bvLine).toBe(24);
  });
  it("leaves the owner's rows alone", () => {
    const rows = [rec(AFTER)];
    expect(gateRecords(rows, true, NOW)).toBe(rows);
  });
  it("re-orders a week's blanked rows by kickoff and name, after its played rows", () => {
    const r = (week: number, away: string, kickoffMs: number, rank: number) =>
      ({
        week,
        away,
        kickoffMs,
        rank,
        bvLine: 1,
        bvGap: 1,
        bvGapZ: 1,
      }) as unknown as RecordRow;
    // Arrives in rank order: an open game ranked first must not stay first.
    const out = gateRecords(
      [
        r(5, "Zeta", AFTER, 1),
        r(5, "Alpha", BEFORE, 2),
        r(5, "Beta", AFTER, 3),
        r(5, "Gamma", AFTER + 1, 4),
        r(4, "Old", BEFORE, 1),
      ],
      false,
      NOW,
    );
    expect(out.map((x) => x.away)).toEqual([
      "Old",
      "Alpha",
      "Beta",
      "Zeta",
      "Gamma",
    ]);
    expect(out.find((x) => x.away === "Alpha")!.rank).toBe(2);
    expect(out.find((x) => x.away === "Zeta")!.rank).toBeNull();
  });
});

describe("gateLedger", () => {
  const led = (kickoff: string | null) =>
    ({ id: 1, kickoff }) as unknown as LedgerRow;
  it("withholds a visitor's rows whose game has not kicked off (or whose kickoff is unknown)", () => {
    const rows = [
      led(new Date(BEFORE).toISOString()),
      led(new Date(AFTER).toISOString()),
      led(null),
    ];
    expect(gateLedger(rows, false, NOW)).toEqual([rows[0]]);
    expect(gateLedger(rows, true, NOW)).toBe(rows);
  });
});
