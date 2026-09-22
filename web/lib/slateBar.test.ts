import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { BET_GAP_PTS, PCT_SHARE, slateBar } from "./verdict";

// The same vectors beatvegas/model/score.py::slate_bar is pinned to
// (tests/test_slate_bar.py). One file, two suites: the first shared golden
// vector in the repo, so the two implementations cannot drift.
const VECTORS = path.resolve(
  __dirname,
  "../../tests/fixtures/slate_bar_vectors.json",
);

describe("slateBar (H-PCT)", () => {
  it("matches the golden vectors shared with the Python side", () => {
    const v = JSON.parse(readFileSync(VECTORS, "utf8")) as {
      share: number;
      cases: { gaps: (number | null)[]; bar: number | null }[];
    };
    expect(v.share).toBe(PCT_SHARE);
    for (const c of v.cases) {
      expect(slateBar(c.gaps)).toBe(c.bar);
    }
  });
  it("keeps the constant only as the fallback", () => {
    expect(BET_GAP_PTS).toBe(1.75);
    expect(slateBar([])).toBeNull();
  });
});
