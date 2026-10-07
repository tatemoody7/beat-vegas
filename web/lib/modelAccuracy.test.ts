import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/prisma", () => ({ prisma: {} }));
vi.mock("next/cache", () => ({ unstable_cache: (f: unknown) => f }));
import { accuracyLine } from "./postmortem";

// The public "average miss" reading on How it works (2026-10-07): one decimal,
// and the sentence names the closer side only when the rounded numbers differ.

describe("accuracyLine", () => {
  const base = { season: 2026, n: 213 };
  it("Hard Rock closer (the season so far: 8.34 vs 8.22)", () => {
    expect(accuracyLine({ ...base, ours: 8.34, hardRock: 8.22 })).toEqual({
      ours: "8.3",
      hardRock: "8.2",
      closer: "hardRock",
    });
  });
  it("ours closer", () => {
    expect(accuracyLine({ ...base, ours: 7.05, hardRock: 7.58 }).closer).toBe(
      "ours",
    );
  });
  it("a tie at one decimal is a tie, not a winner", () => {
    expect(accuracyLine({ ...base, ours: 8.24, hardRock: 8.21 }).closer).toBe(
      "tie",
    );
  });
});
