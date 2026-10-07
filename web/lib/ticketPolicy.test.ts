import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/prisma", () => ({ prisma: {} }));
import { HR_PRICE_MAX_AGE_H } from "./lineCheck";
import { evaluationMode, staleAt } from "./ticketPolicy";

// The pure parts of the one ticket evaluator (2026-10-07). The DB-backed
// whole is exercised against the fixture database by e2e/ledger-integrity.

describe("evaluationMode", () => {
  const now = new Date("2026-10-10T16:00:00Z");
  it("judges a ticket written now, or within the grace, by the live read", () => {
    expect(evaluationMode(null, now)).toBe("live");
    expect(evaluationMode("2026-10-10T15:45:00.000Z", now)).toBe("live");
  });
  it("judges a ticket written more than 30 minutes ago as of its bet time", () => {
    expect(evaluationMode("2026-10-10T15:00:00.000Z", now)).toBe(
      "as_of_bet_time",
    );
  });
});

describe("staleAt (Hard Rock's price must be seen within 6 h of the bet)", () => {
  const betAt = new Date("2026-10-10T16:00:00Z");
  it("is the 6-hour rule Tate set", () => {
    expect(HR_PRICE_MAX_AGE_H).toBe(6);
  });
  it("accepts a quote last seen up to 6 h before the bet time", () => {
    expect(staleAt("2026-10-10 10:00:00", betAt)).toBe(false);
    expect(staleAt("2026-10-10 15:59:00.123", betAt)).toBe(false);
  });
  it("refuses a quote last seen more than 6 h before it", () => {
    expect(staleAt("2026-10-10 09:59:59", betAt)).toBe(true);
    // Tuesday's 4pm build, a Wednesday-noon ticket: refused (Tate's example).
    expect(
      staleAt("2026-10-06 20:05:00", new Date("2026-10-07T16:00:00Z")),
    ).toBe(true);
  });
  it("a sighting after the bet time confirms the quote was still in force", () => {
    // captured Tuesday, re-seen unchanged Saturday: an unchanged poll writes no
    // row, so nothing newer existed in between.
    expect(staleAt("2026-10-10 18:00:00", betAt)).toBe(false);
  });
  it("fails closed on a missing or unreadable time", () => {
    expect(staleAt(null, betAt)).toBe(true);
    expect(staleAt("not a time", betAt)).toBe(true);
  });
});

describe("staleAt, live (M2): a live ticket's price must be seen in the last 6 h", () => {
  const now = new Date("2026-10-08T21:00:00Z");
  it("a quote confirmed by this afternoon's build is fresh", () => {
    expect(staleAt("2026-10-08 20:10:00", now)).toBe(false);
  });
  it("Tuesday's build price on a Thursday evening is stale", () => {
    expect(staleAt("2026-10-06 20:05:00", now)).toBe(true);
  });
});
