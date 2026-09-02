import { describe, expect, it } from "vitest";
import { defaultWeek, weeksOf } from "./week";

const NOW = new Date("2026-09-09T12:00:00Z"); // Wednesday of week 3

describe("defaultWeek", () => {
  it("is the earliest week with a game still to kick off, not the max week posted", () => {
    const games = [
      { week: 2, startDate: "2026-09-05T20:00:00Z" }, // played
      { week: 3, startDate: "2026-09-12T20:00:00Z" }, // upcoming
      { week: 4, startDate: "2026-09-19T20:00:00Z" }, // posted ahead
    ];
    expect(defaultWeek(games, NOW)).toBe(3);
  });
  it("falls back to the latest week once everything has kicked off", () => {
    const games = [
      { week: 1, startDate: "2026-08-29T20:00:00Z" },
      { week: 2, startDate: "2026-09-05T20:00:00Z" },
    ];
    expect(defaultWeek(games, NOW)).toBe(2);
  });
  it("treats an unknown kickoff as upcoming and handles empty input", () => {
    expect(defaultWeek([{ week: 5, startDate: null }], NOW)).toBe(5);
    expect(defaultWeek([], NOW)).toBeNull();
  });
  it("weeksOf lists distinct weeks ascending", () => {
    expect(weeksOf([{ week: 3 }, { week: 1 }, { week: 3 }])).toEqual([1, 3]);
  });
});
