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
  it("real money only on a BET verdict; paper and verdict-less picks pass", () => {
    const watchReal = checkPolicy({ ...pick, verdict: "WATCH" }, ctx);
    expect(watchReal).toMatchObject({ ok: false, status: 409 });
    if (!watchReal.ok) {
      expect(watchReal.error).toBe(
        "WATCH is not a bet — policy allows real money on BET verdicts only. Log it as a paper pick.",
      );
    }
    expect(checkPolicy({ ...pick, verdict: "PASS" }, ctx)).toMatchObject({
      ok: false,
      status: 409,
    });
    expect(
      checkPolicy({ ...pick, verdict: "WATCH", isPaper: true }, ctx),
    ).toEqual({ ok: true });
    expect(checkPolicy({ ...pick, verdict: "BET" }, ctx)).toEqual({ ok: true });
    // Backwards compat: no verdict on the request → not gated.
    expect(checkPolicy({ ...pick, verdict: undefined }, ctx)).toEqual({
      ok: true,
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
