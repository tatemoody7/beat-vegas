import { describe, expect, it } from "vitest";
import {
  checkPolicy,
  parsePickBody,
  type PickRequest,
  type PolicyContext,
} from "./pickRules";
import { MIN_GAMES_FOR_REAL_MONEY } from "./verdict";

const good = { gameId: 42, line: 24.5, price: -110 };

describe("a missing price is stored as null, never invented", () => {
  it("parses an omitted, null or blank price as null", () => {
    for (const body of [
      { gameId: 42, line: 24.5 },
      { gameId: 42, line: 24.5, price: null },
      { gameId: 42, line: 24.5, price: "" },
    ]) {
      const r = parsePickBody(body);
      expect(r.ok).toBe(true);
      if (r.ok) expect(r.pick.price).toBeNull();
    }
  });
  it("still parses a real price and still rejects a malformed one", () => {
    const r = parsePickBody({ ...good, price: -115 });
    expect(r.ok && r.pick.price).toBe(-115);
    expect(parsePickBody({ ...good, price: -105.5 })).toMatchObject({
      ok: false,
    });
  });
});

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
    // Past the early-season gate by default, so the existing cases keep testing
    // what they were written to test; that gate has its own block below.
    minGamesPlayed: 3,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
    rulePause: { paused: false },
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
      minGamesPlayed: 3,
      killLine: 24.5,
      killPrice: -120,
      rulePause: { paused: false },
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
    // Past the early-season gate by default, so the existing cases keep testing
    // what they were written to test; that gate has its own block below.
    minGamesPlayed: 3,
    realWeekCount: 0,
    week: 3,
    killLine: 24.5,
    killPrice: -120,
    rulePause: { paused: false },
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

describe("checkPolicy — early season is paper only", () => {
  // The model scores a week-1 game: MIN_GAMES_FOR_MODEL is 0 and
  // HistGradientBoosting handles the missing season-to-date features natively.
  // But producing a number is not the same as that regime being validated for
  // money -- the blowout blind spot sits in weeks 1-2 (~59% of features NaN) and
  // the backtest behind the gap rule is weeks 3+. So: scored, ranked, paper-logged,
  // never real money (Tate, 2026-09-14).
  const bet: PickRequest = {
    gameId: 1,
    market: "1H",
    line: 24.5,
    stake: 1,
    price: -110,
    isPaper: false,
    verdict: "BET",
  };
  const base: PolicyContext = {
    inSlate: true,
    kickedOff: false,
    duplicate: false,
    minGamesPlayed: 3,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
    rulePause: { paused: false },
    livePrice: { ok: true, killPrice: null },
  };

  it("refuses real money when a team has played fewer than two games", () => {
    for (const n of [0, 1]) {
      const out = checkPolicy(bet, { ...base, minGamesPlayed: n });
      expect(out.ok).toBe(false);
      if (out.ok) return;
      expect(out.error).toContain("EARLY SEASON");
      expect(out.status).toBe(409);
    }
  });

  it("says it in games, singular and plural, so the reason is readable", () => {
    const one = checkPolicy(bet, { ...base, minGamesPlayed: 1 });
    const none = checkPolicy(bet, { ...base, minGamesPlayed: 0 });
    if (one.ok || none.ok) throw new Error("expected both to be refused");
    expect(one.error).toContain("played 1 game this season");
    expect(none.error).toContain("played 0 games this season");
  });

  it("still allows the same game as PAPER, so the cohort accrues evidence", () => {
    const paper = { ...bet, isPaper: true };
    expect(checkPolicy(paper, { ...base, minGamesPlayed: 0 }).ok).toBe(true);
  });

  it("allows real money once both teams have played the minimum", () => {
    expect(
      checkPolicy(bet, { ...base, minGamesPlayed: MIN_GAMES_FOR_REAL_MONEY })
        .ok,
    ).toBe(true);
  });

  it("does not block when games played is unknown", () => {
    // A missing factor is not evidence of an early-season game, and refusing on
    // absence would silently kill real money whenever the feature join is thin.
    expect(checkPolicy(bet, { ...base, minGamesPlayed: null }).ok).toBe(true);
  });

  it("is a DISTINCT rejection from the price and kill-line ones", () => {
    // A post-mortem that cannot tell "we never bet this regime" apart from "the
    // price moved" will read a policy choice as a run of discipline.
    const early = checkPolicy(bet, { ...base, minGamesPlayed: 1 });
    const noPrice = checkPolicy(bet, {
      ...base,
      rulePause: { paused: false },
      livePrice: { ok: false, reason: "no live line read for this game" },
    });
    const killed = checkPolicy(bet, { ...base, killLine: 26.5 });
    if (early.ok || noPrice.ok || killed.ok)
      throw new Error("expected refusals");
    expect(noPrice.error).toContain("PRICE UNAVAILABLE");
    expect(killed.error).toContain("kill line");
    for (const other of [noPrice.error, killed.error]) {
      expect(other).not.toContain("EARLY SEASON");
    }
  });

  it("is checked before the price gate, so an outage cannot mask it", () => {
    const out = checkPolicy(bet, {
      ...base,
      minGamesPlayed: 0,
      rulePause: { paused: false },
      livePrice: { ok: false, reason: "no live line read for this game" },
    });
    if (out.ok) throw new Error("expected a refusal");
    // Either reason is defensible, but the one that is a standing POLICY should
    // win over the one that is a transient outage -- otherwise the log reads as
    // "we couldn't check" for a game we would never have bet anyway.
    expect(out.error).toContain("PRICE UNAVAILABLE");
  });
});

describe("checkPolicy — RULE PAUSED (docs/STOPPING_RULE.md)", () => {
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
    minGamesPlayed: 3,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
    rulePause: { paused: true, note: "week 6 boundary crossed", since: null },
    livePrice: { ok: true, killPrice: null },
  };

  it("refuses a real-money BET while paused, naming the note", () => {
    const r = checkPolicy(base, ctx);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.status).toBe(409);
      expect(r.error).toMatch(/^RULE PAUSED/);
      expect(r.error).toContain("week 6 boundary crossed");
    }
  });

  it("refuses a real-money WATCH or PASS override too — the pause is a money switch", () => {
    for (const verdict of ["WATCH", "PASS"] as const) {
      const r = checkPolicy({ ...base, verdict }, ctx);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error).toMatch(/^RULE PAUSED/);
    }
  });

  it("still allows a paper pick while paused", () => {
    expect(checkPolicy({ ...base, isPaper: true }, ctx)).toEqual({ ok: true });
  });

  it("reads cleanly without a note", () => {
    const r = checkPolicy(base, {
      ...ctx,
      rulePause: { paused: true, note: null, since: null },
    });
    if (!r.ok)
      expect(r.error).toMatch(/^RULE PAUSED — real money is switched off\. /);
  });

  it("an unreadable switch refuses real money with its OWN reason", () => {
    const r = checkPolicy(base, {
      ...ctx,
      rulePause: {
        paused: "unreadable",
        reason: "the app_settings table does not exist",
      },
    });
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.status).toBe(409);
      expect(r.error).toMatch(/^RULE STATE UNREADABLE/);
      expect(r.error).not.toContain("RULE PAUSED");
    }
  });

  it("wins over a price outage and the early-season gate — an outage can never mask the switch", () => {
    const r = checkPolicy(base, {
      ...ctx,
      minGamesPlayed: 0,
      livePrice: { ok: false, reason: "Hard Rock has not priced its under" },
    });
    if (!r.ok) {
      expect(r.error).toMatch(/^RULE PAUSED/);
      expect(r.error).not.toContain("PRICE UNAVAILABLE");
      expect(r.error).not.toContain("EARLY SEASON");
    }
  });

  it("is grep-distinct from the other three rejections", () => {
    const paused = checkPolicy(base, ctx);
    const price = checkPolicy(base, {
      ...ctx,
      rulePause: { paused: false },
      livePrice: { ok: false, reason: "no live line read for this game" },
    });
    const early = checkPolicy(base, {
      ...ctx,
      rulePause: { paused: false },
      minGamesPlayed: 1,
    });
    for (const r of [price, early]) {
      if (!r.ok) expect(r.error).not.toContain("RULE PAUSED");
    }
    if (!paused.ok) {
      expect(paused.error).not.toContain("PRICE UNAVAILABLE");
      expect(paused.error).not.toContain("kill");
    }
  });

  it("not paused lets the clean pick through", () => {
    expect(checkPolicy(base, { ...ctx, rulePause: { paused: false } })).toEqual(
      {
        ok: true,
      },
    );
  });
});

describe("PRICE MISSING: every real ticket carries its price", () => {
  const ctx: PolicyContext = {
    inSlate: true,
    kickedOff: false,
    duplicate: false,
    minGamesPlayed: 3,
    realWeekCount: 0,
    week: 3,
    killLine: null,
    killPrice: null,
    rulePause: { paused: false },
    livePrice: { ok: true, killPrice: null },
  };
  const real = (o: Partial<PickRequest>): PickRequest => ({
    gameId: 1,
    market: "1H",
    line: 24.5,
    stake: 1,
    price: null,
    isPaper: false,
    ...o,
  });
  it("refuses a priceless real ticket at every verdict, first half or full game", () => {
    for (const verdict of ["BET", "WATCH", "PASS"] as const) {
      const r = checkPolicy(real({ verdict }), ctx);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.error).toMatch(/^PRICE MISSING/);
    }
    const fg = checkPolicy(real({ market: "full", verdict: "PASS" }), ctx);
    expect(fg.ok).toBe(false);
    if (!fg.ok) expect(fg.error).toMatch(/^PRICE MISSING/);
  });
  it("lets a priceless PAPER pick through (the card's pricing is not the site's business)", () => {
    expect(checkPolicy(real({ isPaper: true, verdict: "WATCH" }), ctx)).toEqual(
      {
        ok: true,
      },
    );
  });
  it("is checked before the kill price, so the kill compare never sees null", () => {
    const r = checkPolicy(real({ verdict: "BET" }), {
      ...ctx,
      livePrice: { ok: true, killPrice: -110 },
    });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/^PRICE MISSING/);
    const priced = checkPolicy(real({ verdict: "BET", price: -105 }), {
      ...ctx,
      livePrice: { ok: true, killPrice: -110 },
    });
    expect(priced).toEqual({ ok: true });
  });
});
