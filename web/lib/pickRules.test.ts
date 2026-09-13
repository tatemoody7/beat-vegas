import { describe, expect, it } from "vitest";
import {
  checkPolicy,
  parsePickBody,
  type PickRequest,
  type PolicyContext,
} from "./pickRules";

const good = { gameId: 42, line: 24.5, price: -110 };

describe("parsePickBody", () => {
  it("accepts a minimal real 1H pick with flat 1-unit defaults", () => {
    const r = parsePickBody(good);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.pick).toMatchObject({
        gameId: 42,
        market: "1H",
        line: 24.5,
        stake: 1,
        price: -110,
        isPaper: false,
      });
    }
  });
  it("rejects missing gameId / line and a non-integer price", () => {
    expect(parsePickBody({ line: 24.5 })).toMatchObject({
      ok: false,
      status: 400,
    });
    expect(parsePickBody({ gameId: 1 })).toMatchObject({
      ok: false,
      status: 400,
    });
    expect(parsePickBody({ ...good, price: -105.5 })).toMatchObject({
      ok: false,
    });
    expect(parsePickBody({ ...good, price: 50 })).toMatchObject({ ok: false });
  });
  it("paper picks are 1 flat unit regardless of the client's stake", () => {
    const r = parsePickBody({ ...good, isPaper: true, stake: 0 });
    expect(r.ok && r.pick.stake).toBe(1);
    const r2 = parsePickBody({ ...good, isPaper: true, stake: 3 });
    expect(r2.ok && r2.pick.stake).toBe(1);
  });
  it("real picks are ALWAYS 1 flat unit — the client's stake is ignored, never rejected", () => {
    for (const stake of [3, 0, -2, null, "abc", NaN]) {
      const r = parsePickBody({ ...good, stake });
      expect(r.ok).toBe(true);
      expect(r.ok && r.pick.stake).toBe(1);
    }
  });
  it("rejects a real-money full-game pick but allows it as paper", () => {
    const real = parsePickBody({ ...good, market: "full" });
    expect(real.ok).toBe(false);
    if (!real.ok) expect(real.error).toMatch(/first-half unders only/);
    const paper = parsePickBody({ ...good, market: "full", isPaper: true });
    expect(paper.ok).toBe(true);
  });
  it("stores the verdict snapshot and rejects unknown reasons", () => {
    const r = parsePickBody({
      ...good,
      verdict: "BET",
      reason: "model_gap",
      gap: 2.2,
      ev: 0.011,
      hrLine: 24.5,
    });
    expect(r.ok && r.pick).toMatchObject({
      verdict: "BET",
      reason: "model_gap",
      gap: 2.2,
      ev: 0.011,
      hrLine: 24.5,
    });
    expect(parsePickBody({ ...good, reason: "vibes" })).toMatchObject({
      ok: false,
    });
    expect(parsePickBody({ ...good, verdict: "MAYBE" })).toMatchObject({
      ok: false,
    });
    expect(parsePickBody({ ...good, gap: "big" })).toMatchObject({ ok: false });
  });
});

describe("checkPolicy", () => {
  const pick: PickRequest = {
    gameId: 42,
    market: "1H",
    line: 24.5,
    stake: 1,
    price: -110,
    isPaper: false,
  };
  // A verified live price is the DEFAULT here so the existing cases keep
  // testing what they were written to test. The fail-closed path has its own
  // describe block below.
  const ctx: PolicyContext = {
    inSlate: true,
    kickedOff: false,
    duplicate: false,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
    livePrice: { ok: true, killPrice: null },
  };
  it("passes a clean pick", () => {
    expect(checkPolicy(pick, ctx)).toEqual({ ok: true });
  });
  it("enforces the 5-bet weekly cap on real 1H picks only", () => {
    const r = checkPolicy(pick, { ...ctx, realWeekCount: 5 });
    expect(r).toMatchObject({ ok: false, status: 409 });
    if (!r.ok) expect(r.error).toMatch(/^5 real-money bets are already logged/);
    expect(checkPolicy(pick, { ...ctx, realWeekCount: 4 })).toEqual({
      ok: true,
    });
    expect(
      checkPolicy({ ...pick, isPaper: true }, { ...ctx, realWeekCount: 9 }),
    ).toEqual({ ok: true });
  });
  it("real money is accepted on any verdict (WATCH/PASS = off-policy, still recorded)", () => {
    expect(checkPolicy({ ...pick, verdict: "WATCH" }, ctx)).toEqual({
      ok: true,
    });
    expect(checkPolicy({ ...pick, verdict: "PASS" }, ctx)).toEqual({
      ok: true,
    });
    expect(
      checkPolicy({ ...pick, verdict: "WATCH", isPaper: true }, ctx),
    ).toEqual({ ok: true });
    expect(checkPolicy({ ...pick, verdict: "BET" }, ctx)).toEqual({ ok: true });
    expect(checkPolicy({ ...pick, verdict: undefined }, ctx)).toEqual({
      ok: true,
    });
  });
  describe("kill numbers (the card's line/price floor on a real BET)", () => {
    const bet: PickRequest = {
      ...pick,
      verdict: "BET",
      line: 24.5,
      price: -110,
    };
    const kills: PolicyContext = {
      ...ctx,
      killLine: 24.5,
      killPrice: -120,
      livePrice: { ok: true, killPrice: -120 },
    };
    it("rejects a real 1H BET below the kill line with a 409 that names the kill", () => {
      const r = checkPolicy({ ...bet, line: 24 }, kills);
      expect(r).toMatchObject({ ok: false, status: 409 });
      if (!r.ok) {
        expect(r.error).toMatch(/kill line/i);
        expect(r.error).toMatch(/u24\.5/);
        expect(r.error).toMatch(/u24\b/);
        expect(r.error).toMatch(/a different bet/i);
        expect(r.error).toMatch(/pass on it/i);
      }
    });
    it("accepts a line exactly at the kill line", () => {
      expect(checkPolicy({ ...bet, line: 24.5 }, kills)).toEqual({ ok: true });
      expect(checkPolicy({ ...bet, line: 25 }, kills)).toEqual({ ok: true });
    });
    it("rejects a price worse than the kill price (American odds, lower = worse)", () => {
      const r = checkPolicy({ ...bet, price: -125 }, kills);
      expect(r).toMatchObject({ ok: false, status: 409 });
      if (!r.ok) {
        expect(r.error).toMatch(/-120/);
        expect(r.error).toMatch(/a different bet/i);
        expect(r.error).toMatch(/pass on it/i);
      }
      expect(checkPolicy({ ...bet, price: 105 }, kills)).toEqual({ ok: true });
    });
    it("accepts a price exactly at the kill price", () => {
      expect(checkPolicy({ ...bet, price: -120 }, kills)).toEqual({ ok: true });
    });
    it("exempts paper picks", () => {
      expect(
        checkPolicy({ ...bet, line: 23, price: -130, isPaper: true }, kills),
      ).toEqual({ ok: true });
    });
    it("exempts WATCH/PASS (an owner override is off-policy, not the card's bet)", () => {
      expect(
        checkPolicy({ ...bet, line: 23, verdict: "WATCH" }, kills),
      ).toEqual({ ok: true });
      expect(checkPolicy({ ...bet, line: 23, verdict: "PASS" }, kills)).toEqual(
        { ok: true },
      );
      expect(
        checkPolicy({ ...bet, line: 23, verdict: undefined }, kills),
      ).toEqual({ ok: true });
    });
    it("is a no-op when the card has no kill numbers", () => {
      expect(checkPolicy({ ...bet, line: 20, price: -140 }, ctx)).toEqual({
        ok: true,
      });
      expect(
        checkPolicy({ ...bet, line: 20 }, { ...ctx, killPrice: -120 }),
      ).toEqual({ ok: true });
    });
    it("runs after the duplicate check and before the cap", () => {
      expect(
        checkPolicy({ ...bet, line: 24 }, { ...kills, duplicate: true }),
      ).toMatchObject({ status: 409, error: expect.stringMatching(/already/) });
      expect(
        checkPolicy({ ...bet, line: 24 }, { ...kills, realWeekCount: 5 }),
      ).toMatchObject({ error: expect.stringMatching(/kill line/i) });
    });
  });
  it("rejects off-slate, post-kickoff and duplicate picks", () => {
    expect(checkPolicy(pick, { ...ctx, inSlate: false })).toMatchObject({
      status: 400,
    });
    expect(checkPolicy(pick, { ...ctx, kickedOff: true })).toMatchObject({
      status: 409,
    });
    expect(checkPolicy(pick, { ...ctx, duplicate: true })).toMatchObject({
      status: 409,
    });
  });
});

// --- fail closed: no verified live price, no real money ----------------------
//
// The card is built on a Tuesday and the bet is placed on a Saturday, so the
// card's killPrice is a stale number by the time it is enforced. It may be
// shown for context; it must never authorize a wager. This block is the pin.
describe("checkPolicy — PRICE UNAVAILABLE", () => {
  const base: PickRequest = {
    gameId: 1,
    market: "1H",
    line: 24.5,
    stake: 1,
    price: -110,
    isPaper: false,
    verdict: "BET",
  };
  const ctx: PolicyContext = {
    inSlate: true,
    kickedOff: false,
    duplicate: false,
    realWeekCount: 0,
    week: 3,
    killLine: 24.5,
    killPrice: -120,
    livePrice: { ok: false, reason: "Hard Rock has not priced its under" },
  };

  it("refuses a real 1H BET when the live price cannot be verified", () => {
    const r = checkPolicy(base, ctx);
    expect(r).toMatchObject({ ok: false, status: 409 });
    if (!r.ok) {
      expect(r.error).toMatch(/PRICE UNAVAILABLE/);
      expect(r.error).toMatch(/Hard Rock has not priced its under/);
    }
  });

  it("does not fall back to the card's cached kill price", () => {
    // -105 beats the cached kill of -120, so the ONLY thing that can refuse
    // this pick is the missing live read. If the cached number were trusted,
    // this would log.
    const r = checkPolicy({ ...base, price: -105 }, ctx);
    expect(r).toMatchObject({ ok: false, status: 409 });
    if (!r.ok) expect(r.error).toMatch(/PRICE UNAVAILABLE/);
  });

  it("says WHY, and distinguishes 'cannot check' from 'too expensive'", () => {
    const cannotCheck = checkPolicy(base, ctx);
    const tooExpensive = checkPolicy(
      { ...base, price: -200 },
      { ...ctx, livePrice: { ok: true, killPrice: -120 } },
    );
    expect(cannotCheck.ok).toBe(false);
    expect(tooExpensive.ok).toBe(false);
    if (!cannotCheck.ok && !tooExpensive.ok) {
      // An outage must never read as a run of discipline in the post-mortem.
      expect(cannotCheck.error).not.toEqual(tooExpensive.error);
      expect(tooExpensive.error).not.toMatch(/PRICE UNAVAILABLE/);
      expect(tooExpensive.error).toMatch(/kill price/i);
    }
  });

  it("still allows paper, and still allows an off-policy WATCH override", () => {
    expect(checkPolicy({ ...base, isPaper: true }, ctx)).toEqual({ ok: true });
    expect(checkPolicy({ ...base, verdict: "WATCH" }, ctx)).toEqual({
      ok: true,
    });
  });

  it("prefers the live kill price over the card's when both exist", () => {
    // Card says -120 (stale, from Tuesday); the market has since moved and the
    // live break-even is -105. A -110 ticket clears the stale number and fails
    // the live one, and the live one is what the bettor is being offered.
    const r = checkPolicy(
      { ...base, price: -110 },
      { ...ctx, livePrice: { ok: true, killPrice: -105 } },
    );
    expect(r).toMatchObject({ ok: false, status: 409 });
    if (!r.ok) expect(r.error).toMatch(/-105/);
  });
});
