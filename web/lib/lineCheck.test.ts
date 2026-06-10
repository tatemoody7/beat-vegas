import { expect, test } from "vitest";
import { devigTwoWay, evUnder } from "@/lib/devig";
import { evVerdictFor } from "@/lib/lineCheck";

// The EV verdict bands.
test("evVerdictFor bands", () => {
  expect(evVerdictFor(null)).toBe("na");
  expect(evVerdictFor(0.01)).toBe("pos");
  expect(evVerdictFor(0.0)).toBe("fair");
  expect(evVerdictFor(-0.045)).toBe("neg"); // -110 into a fair 0.5 market
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

test("everyone at -110 -> HR's under just pays the vig", () => {
  const marketFairUnder = devigTwoWay(-110, -110).fairUnder; // 0.5
  const ev = evUnder(marketFairUnder, -110);
  expect(ev).toBeLessThan(0);
  expect(evVerdictFor(ev)).toBe("neg");
});
