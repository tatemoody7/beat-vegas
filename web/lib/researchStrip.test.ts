import { describe, expect, it } from "vitest";
import { stripLine } from "@/app/components/ResearchStrip";
import { cardsFor, type HypothesisCard } from "./research";
import type { ArmPosition } from "./armPositions";

const pos = (id: string, over: Partial<ArmPosition>): [string, ArmPosition] => [
  id,
  {
    hypothesis: id,
    standard: "sprt",
    read_date: "2026-10-19",
    run_id: "1",
    state: "running",
    label: "IN FORWARD TEST",
    logged: 0,
    readings: 0,
    weeks: 0,
    excluded: 0,
    pending: 0,
    needed: 30,
    llr: 0,
    mean_ev: null,
    ev_lo: null,
    ev_hi: null,
    next_read: "2026-10-26",
    readAt: new Date("2026-10-19T12:05:00Z"),
    freshness: "current",
    sufficient: false,
    ...over,
  },
];

describe("the research strip line", () => {
  it("says not yet read before any Monday row", () => {
    const cards: HypothesisCard[] = cardsFor(new Map());
    expect(stripLine(cards)).toBe(
      "six paper strategies judged against the closing price · not yet read",
    );
  });
  it("counts readings toward 30 and names the next read", () => {
    const cards = cardsFor(
      new Map([
        pos("H-ARM-1HU", { readings: 12, logged: 14 }),
        pos("H-ARM-1HO", { readings: 1 }),
      ]),
    );
    expect(stripLine(cards)).toBe(
      "six paper strategies judged against the closing price · up to 12 of 30 readings · next read Mon Oct 26",
    );
    const zero = cardsFor(new Map([pos("H-ARM-FGU", { readings: 0 })]));
    expect(stripLine(zero)).toBe(
      "six paper strategies judged against the closing price · 0 of 30 readings · next read Mon Oct 26",
    );
  });
});
