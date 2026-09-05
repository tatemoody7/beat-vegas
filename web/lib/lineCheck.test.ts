import { expect, test } from "vitest";
import { devigTwoWay, evUnder } from "@/lib/devig";
import { evVerdictFor } from "@/lib/lineCheck";
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
