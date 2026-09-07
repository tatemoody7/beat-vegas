import { describe, expect, it } from "vitest";
import { checkPolicy, parsePickBody, type PickRequest } from "./pickRules";

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
    if (!real.ok) expect(real.error).toMatch(/context only/);
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
  const ctx = {
    inSlate: true,
    kickedOff: false,
    duplicate: false,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
  };
  it("passes a clean pick", () => {
    expect(checkPolicy(pick, ctx)).toEqual({ ok: true });
  });
  it("enforces the 5-bet weekly cap on real 1H picks only", () => {
    const r = checkPolicy(pick, { ...ctx, realWeekCount: 5 });
    expect(r).toMatchObject({ ok: false, status: 409 });
    if (!r.ok) expect(r.error).toMatch(/Weekly cap reached: 5/);
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
    const kills = { ...ctx, killLine: 24.5, killPrice: -120 };
    it("rejects a real 1H BET below the kill line with a 409 that names the kill", () => {
      const r = checkPolicy({ ...bet, line: 24 }, kills);
      expect(r).toMatchObject({ ok: false, status: 409 });
      if (!r.ok) {
        expect(r.error).toMatch(/kill line/i);
        expect(r.error).toMatch(/u24\.5/);
        expect(r.error).toMatch(/u24\b/);
        expect(r.error).toMatch(/is not the same bet the card rated/i);
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
        expect(r.error).toMatch(/is not the same bet the card rated/i);
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
