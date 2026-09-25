import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { buildWeek } from "../e2e/fixture/week.mjs";
import {
  breakEvenPrice as portedBreakEvenPrice,
  buildExpected,
  consensusFor,
  deriveReason,
  devigTwoWay as portedDevigTwoWay,
  edgeFor,
  evUnder as portedEvUnder,
  lineCheckFor,
  lineUsedFor,
  priceSentence as portedPriceSentence,
  slateBar as portedSlateBar,
} from "../e2e/fixture/expected.mjs";
import { edgeScore, type EdgeInput } from "./edge";
import {
  deriveReason as tsDeriveReason,
  priceSentence,
  slateBar,
} from "./verdict";
import { devigTwoWay, evUnder } from "./devig";
import { breakEvenPrice } from "./edge";

// e2e/fixture/expected.mjs is a plain-JS PORT of the pure rules in this
// directory, because seed.mjs runs under `node` and must write a card payload
// that agrees with what the board computes live. This holds the port to the
// originals on the fixture itself: if edge.ts, verdict.ts or lineCheck.ts
// change, the fixture's expectations change with them or this fails.

const VECTORS = path.resolve(
  __dirname,
  "../../tests/fixtures/slate_bar_vectors.json",
);

const week = buildWeek(new Date());
const expected = buildExpected(week);

describe("the e2e fixture port agrees with the TypeScript rules", () => {
  it("slateBar matches lib/verdict.ts on the shared golden vectors", () => {
    const v = JSON.parse(readFileSync(VECTORS, "utf8")) as {
      cases: { gaps: (number | null)[]; bar: number | null }[];
    };
    for (const c of v.cases) {
      expect(portedSlateBar(c.gaps)).toBe(slateBar(c.gaps));
      expect(portedSlateBar(c.gaps)).toBe(c.bar);
    }
  });

  it("the devig / EV / kill-price arithmetic matches", () => {
    for (const [over, under] of [
      [-110, -110],
      [-112, -108],
      [105, -135],
      [-105, -115],
    ]) {
      const fair = devigTwoWay(over, under).fairUnder;
      expect(portedDevigTwoWay(over, under).fairUnder).toBeCloseTo(fair, 12);
      for (const price of [-105, -110, -115, -135, 100]) {
        expect(portedEvUnder(fair, price)).toBeCloseTo(
          evUnder(fair, price),
          12,
        );
      }
      expect(portedBreakEvenPrice(fair)).toBe(breakEvenPrice(fair));
    }
  });

  it.each(week.games.map((g) => [g.id, g] as const))(
    "game %i: edgeScore, priceSentence and deriveReason agree with the port",
    (_id, g) => {
      const check = lineCheckFor(g);
      const cons = consensusFor(g);
      const ported = edgeFor(g, expected.bar, check, cons);
      const input: EdgeInput = {
        away: g.away,
        home: g.home,
        underScore: g.underScore,
        bvLine: g.bv,
        liveLine: cons.cur,
        fallbackLine: lineUsedFor(g),
        gap:
          cons.cur !== null ? Math.round((cons.cur - g.bv) * 100) / 100 : null,
        hrLine: check?.hrLine ?? null,
        hrUnderPrice: check?.hrUnderPrice ?? null,
        ev: check?.ev ?? null,
        evVerdict: (check?.evVerdict ?? "na") as EdgeInput["evVerdict"],
        fhShare: null,
        qbOut: false,
        qbOutDetail: null,
        minGamesPlayed: Math.min(g.gamesPlayed.home, g.gamesPlayed.away),
        bvAdjust: null,
        bvAdjustReason: null,
        factorBoard: null,
        marketLine: cons.cur,
        bestLine: check?.best ?? null,
        marketFairUnder: check?.marketFairUnder ?? null,
        context: {
          combinedSecPlay: null,
          windMph: null,
          dome: null,
          spread: null,
          fhPrior: null,
        },
        bar: expected.bar,
        hrCentred: check?.hrCentred ?? null,
        hrLive: check?.hrLive ?? null,
      };
      const ts = edgeScore(input);
      expect(ported.tier).toBe(ts.tier);
      expect(ported.blocker).toBe(ts.blocker);
      expect(ported.score).toBe(ts.score);
      expect(ported.gap).toBe(ts.gap);
      expect(ported.lineBasis).toBe(ts.lineBasis);
      expect(ported.killLine).toBe(ts.kill.line);
      expect(ported.killPrice).toBe(ts.kill.price);
      expect(ported.action).toBe(ts.action);
      expect(ported.verdict).toBe(ts.verdict.verdict);
      expect(ported.hrGap).toBe(ts.verdict.hrGap);
      expect(ported.reason).toBe(ts.verdict.reason);
      expect(portedPriceSentence(input)).toBe(priceSentence(input));
      expect(deriveReason(true, ported.hrGap, false, expected.bar)).toBe(
        tsDeriveReason(true, ts.verdict.hrGap, false, expected.bar),
      );
    },
  );

  it("lays the week out as the specs assume", () => {
    expect(expected.bar).toBe(3.5);
    expect(expected.counts).toEqual({ bet: 2, edge: 4, pass: 7 });
    expect(expected.card.counts).toMatchObject({ bet: 2, edge: 4, pass: 6 });
    expect(expected.betIds).toEqual([900001, 900002]);
    expect(expected.playedIds).toEqual([900012]);
    expect(expected.rankOrder).toHaveLength(12);
    expect(expected.barLine).toMatch(/^This week’s bar: 3\.50 pts — /);
    // Every upcoming game is still upcoming for at least the lead the week promises.
    const soonest = Math.min(
      ...week.games.filter((g) => !g.played).map((g) => g.kick.getTime()),
    );
    expect(soonest - week.now.getTime()).toBeGreaterThanOrEqual(
      12 * 3_600_000 - 60_000,
    );
    // The card's slot is one of the four scheduled builds, never manual.
    expect(["tue_pm", "thu_pm", "fri_pm", "sat_am"]).toContain(
      expected.card.slot,
    );
  });
});
