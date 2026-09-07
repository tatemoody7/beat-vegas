import { expect, test } from "vitest";
import { devigTwoWay, evUnder } from "@/lib/devig";
import { evVerdictFor, marketFairUnderAt, type FairObs } from "@/lib/lineCheck";
import { EV_FLOOR } from "@/lib/verdict";

// The EV verdict bands: > +0.5% pos, < EV_FLOOR (-5%) neg, else fair.
test("evVerdictFor bands", () => {
  expect(EV_FLOOR).toBe(-0.05);
  expect(evVerdictFor(null)).toBe("na");
  expect(evVerdictFor(0.01)).toBe("pos");
  expect(evVerdictFor(0.006)).toBe("pos");
  expect(evVerdictFor(0.005)).toBe("fair"); // the pos band is strictly above +0.5%
  expect(evVerdictFor(0.0)).toBe("fair");
  expect(evVerdictFor(-0.02)).toBe("fair"); // the old floor no longer bites
  expect(evVerdictFor(-0.045)).toBe("fair"); // -110 into a fair 0.5 market: standard juice
  expect(evVerdictFor(-0.05)).toBe("fair"); // the floor itself is still fair
  expect(evVerdictFor(-0.0501)).toBe("neg");
  expect(evVerdictFor(-0.065)).toBe("neg"); // -115 into a fair 0.5 market
});

// End-to-end: replicate getLineCheck's EV calc (consensus no-vig fair-under at a
// comparable number -> EV of HR's under price) on two scenarios.
test("market shading the under under HR's price reads +EV", () => {
  // Other books price the under as a clear favorite (under -150 / over +130) at
  // HR's number; HR offers the under at -110. HR is the generous price.
  const marketFairUnder = devigTwoWay(130, -150).fairUnder;
  const ev = evUnder(marketFairUnder, -110);
  expect(ev).toBeGreaterThan(0);
  expect(evVerdictFor(ev)).toBe("pos");
});

test("everyone at -110 -> HR's under just pays standard vig, a fair price", () => {
  const marketFairUnder = devigTwoWay(-110, -110).fairUnder; // 0.5
  const ev = evUnder(marketFairUnder, -110);
  expect(ev).toBeCloseTo(-0.0455, 3);
  expect(ev).toBeLessThan(0);
  expect(ev).toBeGreaterThanOrEqual(EV_FLOOR);
  expect(evVerdictFor(ev)).toBe("fair");
  // A nickel worse than the market is outside the floor.
  const ev115 = evUnder(marketFairUnder, -115);
  expect(ev115).toBeCloseTo(-0.0652, 3);
  expect(evVerdictFor(ev115)).toBe("neg");
});

// Exchange-first fair price at Hard Rock's number (mirrors beatvegas/card.py
// market_read, so the site and the card agree on EV).
const obs = (
  line: number,
  over: number | null,
  under: number | null,
): FairObs => ({
  line,
  overPrice: over,
  underPrice: under,
});

test("an exchange quoting Hard Rock's exact line IS the fair price", () => {
  const byBook = new Map<string, FairObs>([
    ["hardrockbet", obs(24.5, -110, -110)],
    ["draftkings", obs(24.5, 100, -120)],
    ["kalshi", obs(24.5, 100, -102)],
  ]);
  const r = marketFairUnderAt(24.5, byBook);
  expect(r.source).toBe("exchange");
  expect(r.fairUnder).toBeCloseTo(devigTwoWay(100, -102).fairUnder, 12);
  // two exchanges at the line -> the mean of their de-vigged unders
  byBook.set("novig", obs(24.5, -104, 102));
  const k = devigTwoWay(100, -102).fairUnder;
  const n = devigTwoWay(-104, 102).fairUnder;
  expect(marketFairUnderAt(24.5, byBook).fairUnder).toBeCloseTo(
    (k + n) / 2,
    12,
  );
});

test("an exchange at another line falls back to the book median within half a point", () => {
  const byBook = new Map<string, FairObs>([
    ["hardrockbet", obs(24.5, -110, -110)],
    ["draftkings", obs(24.5, 100, -120)],
    ["fanduel", obs(25.0, 100, -120)], // inside the window
    ["betmgm", obs(25.5, -105, -115)], // a full point away: out
    ["kalshi", obs(25.0, 100, -102)], // half a point off: not the same market
  ]);
  const r = marketFairUnderAt(24.5, byBook);
  expect(r.source).toBe("books");
  expect(r.fairUnder).toBeCloseTo(12 / 23, 12);
});

test("Hard Rock, fliff, the synthetic aggregate and exchanges never enter the book median", () => {
  const byBook = new Map<string, FairObs>([
    ["hardrockbet", obs(24.5, -110, -105)],
    ["draftkings", obs(24.5, -110, -110)],
    ["fliff", obs(24.5, 100, 100)], // would drag the median off 0.5
    ["consensus", obs(24.5, 100, 100)],
    ["Fliff", obs(25.0, 100, 100)], // casing never leaks a book through
  ]);
  const r = marketFairUnderAt(24.5, byBook);
  expect(r.source).toBe("books");
  expect(r.fairUnder).toBeCloseTo(0.5, 12);
});

test("no comparable price -> null (the card's no_fair_price gate)", () => {
  const alone = new Map<string, FairObs>([
    ["hardrockbet", obs(24.5, -110, -110)],
  ]);
  expect(marketFairUnderAt(24.5, alone)).toEqual({
    fairUnder: null,
    source: null,
  });
  const oneSided = new Map<string, FairObs>([
    ["hardrockbet", obs(24.5, -110, -110)],
    ["kalshi", obs(24.5, null, -102)],
  ]);
  expect(marketFairUnderAt(24.5, oneSided).fairUnder).toBeNull();
  expect(marketFairUnderAt(null, alone).fairUnder).toBeNull();
});
