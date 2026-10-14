import { describe, expect, it } from "vitest";
import {
  freshnessOf,
  newestByHypothesis,
  utcFrom,
  type ArmPositionRow,
} from "./armPositions";

const row = (over: Partial<ArmPositionRow>): ArmPositionRow => ({
  hypothesis: "H-ARM-1HU",
  standard: "sprt",
  read_date: "2026-10-19",
  read_at: "2026-10-19 12:05:00",
  run_id: "1",
  state: "running",
  label: "IN FORWARD TEST",
  logged: 12,
  readings: 9,
  weeks: 1,
  excluded: 3,
  pending: 0,
  needed: 30,
  llr: 0.4,
  mean_ev: -0.012,
  ev_lo: null,
  ev_hi: null,
  next_read: "2026-10-26",
  ...over,
});

describe("armPositions", () => {
  it("reads the naive timestamp as UTC, never local time", () => {
    expect(utcFrom("2026-10-19 12:05:00").toISOString()).toBe(
      "2026-10-19T12:05:00.000Z",
    );
    expect(utcFrom("2026-10-19T12:05:00Z").toISOString()).toBe(
      "2026-10-19T12:05:00.000Z",
    );
  });
  it("keeps the newest row per hypothesis and marks freshness and sufficiency", () => {
    const now = new Date("2026-10-21T00:00:00Z");
    const m = newestByHypothesis(
      [
        row({ read_at: "2026-10-12 12:00:00", readings: 2, run_id: "old" }),
        row({ read_at: "2026-10-19 12:05:00", readings: 9, run_id: "new" }),
        row({
          hypothesis: "H-PRICE-HR",
          standard: "pricing",
          readings: 41,
          needed: 40,
          read_at: "2026-10-05 12:00:00",
        }),
      ],
      now,
    );
    expect(m.get("H-ARM-1HU")?.run_id).toBe("new");
    expect(m.get("H-ARM-1HU")?.freshness).toBe("current");
    expect(m.get("H-ARM-1HU")?.sufficient).toBe(false);
    expect(m.get("H-PRICE-HR")?.freshness).toBe("outdated"); // 16 days old
    expect(m.get("H-PRICE-HR")?.sufficient).toBe(true);
  });
  it("calls a read older than eight days outdated, not before", () => {
    const read = new Date("2026-10-19T12:00:00Z");
    expect(freshnessOf(read, new Date("2026-10-27T11:00:00Z"))).toBe("current");
    expect(freshnessOf(read, new Date("2026-10-27T13:00:00Z"))).toBe(
      "outdated",
    );
  });
});
