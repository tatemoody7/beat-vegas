import { expect, test } from "vitest";
import { kellyFraction, suggestedUnits } from "@/lib/kelly";

test("kellyFraction: positive only with a real edge", () => {
  // Fair under 0.55 at -110 (b ~ 0.909): f = (0.909*0.55 - 0.45)/0.909 ~ 0.055.
  expect(kellyFraction(0.55, -110)).toBeCloseTo(0.055, 2);
  // Fair under 0.50 at -110: paying the vig -> no edge -> 0.
  expect(kellyFraction(0.5, -110)).toBe(0);
  // A worse-than-fair price -> 0.
  expect(kellyFraction(0.45, -110)).toBe(0);
});

test("suggestedUnits: quarter-Kelly, bankroll-relative, capped", () => {
  // quarter of 0.055 = 0.01375 of bankroll; at 1u=1% -> ~1.375 units.
  expect(suggestedUnits(0.55, -110)).toBeCloseTo(1.375, 2);
  // No edge -> 0 units.
  expect(suggestedUnits(0.5, -110)).toBe(0);
  // A huge edge is capped (uncertain edges shouldn't blow up the stake).
  expect(suggestedUnits(0.95, -110, { capUnits: 3 })).toBe(3);
  // Half-Kelly suggests more than quarter-Kelly for the same edge.
  expect(suggestedUnits(0.55, -110, { fraction: 0.5 })).toBeGreaterThan(
    suggestedUnits(0.55, -110, { fraction: 0.25 }),
  );
});
