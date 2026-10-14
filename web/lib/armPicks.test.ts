import { describe, expect, it } from "vitest";
import { groupForward, opportunitiesFrom, type ArmPick } from "./armPicks";

const pick = (over: Partial<ArmPick>): ArmPick => ({
  arm: "H-ARM-1HO",
  id: 1,
  week: 7,
  away: "FIU",
  home: "Jacksonville State",
  market: "1H",
  side: "over",
  line: 20.5,
  price: -125,
  result: "over",
  units: 0.8,
  evCons: null,
  consExcluded: "far_lines",
  placedAt: "2026-10-13 20:51:39.533351",
  ...over,
});

describe("armPicks", () => {
  it("keeps every arm in slot order and drops picks placed before the arm's start", () => {
    const m = groupForward([
      pick({ id: 1 }), // exactly ARMS_START: forward
      pick({ id: 2, placedAt: "2026-10-09 20:17:48.434122" }), // development
      pick({ id: 3, arm: "H-ARM-WX1H", placedAt: "2026-10-10 00:00:00" }), // its own backstop
      pick({ id: 4, arm: "H-RANDOM" }), // not a registered arm
    ]);
    expect([...m.keys()]).toEqual([
      "H-ARM-1HU",
      "H-ARM-1HO",
      "H-ARM-FGU",
      "H-ARM-WX1H",
      "H-ARM-WXFG",
      "H-ARM-HT1H",
    ]);
    expect(m.get("H-ARM-1HO")!.map((p) => p.id)).toEqual([1]);
    expect(m.get("H-ARM-WX1H")!.map((p) => p.id)).toEqual([3]);
    expect(m.get("H-ARM-1HU")).toEqual([]);
  });
  it("reads the opportunities the pricing row carries, and none from an old verdict-only row", () => {
    const opp = { market: "1H_total", game: "A @ B", side: "under" };
    expect(
      opportunitiesFrom(JSON.stringify({ verdict: {}, opportunities: [opp] })),
    ).toEqual([opp]);
    expect(
      opportunitiesFrom(JSON.stringify({ verdict: "insufficient" })),
    ).toEqual([]);
    expect(opportunitiesFrom(null)).toEqual([]);
    expect(opportunitiesFrom("not json")).toEqual([]);
  });
});
