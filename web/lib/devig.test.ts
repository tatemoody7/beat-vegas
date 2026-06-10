import { expect, test } from "vitest";
import { americanToProb, devigTwoWay, evUnder } from "@/lib/devig";

// Shared vectors with tests/test_devig.py — keep the two in sync.

test("americanToProb", () => {
  expect(americanToProb(-110)).toBeCloseTo(0.52381, 4);
  expect(americanToProb(120)).toBeCloseTo(0.45455, 4);
  expect(americanToProb(100)).toBeCloseTo(0.5, 9);
});

test("symmetric -110/-110 -> fair 0.5 each, hold ~4.55%", () => {
  const { fairOver, fairUnder, hold } = devigTwoWay(
    -110,
    -110,
    "multiplicative",
  );
  expect(fairOver).toBeCloseTo(0.5, 6);
  expect(fairUnder).toBeCloseTo(0.5, 6);
  expect(hold).toBeCloseTo(0.0476, 3);
});

test.each(["multiplicative", "power", "shin"] as const)(
  "fair probs sum to one (%s)",
  (method) => {
    const { fairOver, fairUnder } = devigTwoWay(-130, 110, method);
    expect(fairOver + fairUnder).toBeCloseTo(1.0, 6);
  },
);

test("under favored pushes fair under above half", () => {
  const { fairUnder } = devigTwoWay(110, -130, "multiplicative");
  expect(fairUnder).toBeGreaterThan(0.5);
});

test("methods diverge on a lopsided line", () => {
  const mult = devigTwoWay(-300, 240, "multiplicative").fairUnder;
  const sh = devigTwoWay(-300, 240, "shin").fairUnder;
  const pw = devigTwoWay(-300, 240, "power").fairUnder;
  expect(Math.abs(mult - sh) > 1e-3 || Math.abs(mult - pw) > 1e-3).toBe(true);
});

test("symmetric methods agree", () => {
  const mult = devigTwoWay(-110, -110, "multiplicative").fairUnder;
  const sh = devigTwoWay(-110, -110, "shin").fairUnder;
  const pw = devigTwoWay(-110, -110, "power").fairUnder;
  expect(mult).toBeCloseTo(sh, 4);
  expect(mult).toBeCloseTo(pw, 4);
});

test("evUnder sign", () => {
  expect(evUnder(0.55, -110)).toBeGreaterThan(0);
  expect(evUnder(0.5, -110)).toBeLessThan(0);
  expect(evUnder(0.5, 100)).toBeCloseTo(0.0, 9);
});

test("unknown method throws", () => {
  // @ts-expect-error testing runtime guard
  expect(() => devigTwoWay(-110, -110, "bogus")).toThrow();
});
