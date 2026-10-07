import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/prisma", () => ({ prisma: {} }));
import { HR_PRICE_MAX_AGE_H } from "./lineCheck";
import { evaluationMode, staleAtBet } from "./ticketPolicy";

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

describe("staleAtBet (Hard Rock's price must be seen within 6 h of the bet)", () => {
  const betAt = new Date("2026-10-10T16:00:00Z");
  it("is the 6-hour rule Tate set", () => {
    expect(HR_PRICE_MAX_AGE_H).toBe(6);
  });
  it("accepts a quote last seen up to 6 h before the bet time", () => {
    expect(staleAtBet("2026-10-10 10:00:00", betAt)).toBe(false);
    expect(staleAtBet("2026-10-10 15:59:00.123", betAt)).toBe(false);
  });
  it("refuses a quote last seen more than 6 h before it", () => {
    expect(staleAtBet("2026-10-10 09:59:59", betAt)).toBe(true);
    // Tuesday's 4pm build, a Wednesday-noon ticket: refused (Tate's example).
    expect(
      staleAtBet("2026-10-06 20:05:00", new Date("2026-10-07T16:00:00Z")),
    ).toBe(true);
  });
  it("a sighting after the bet time confirms the quote was still in force", () => {
    // captured Tuesday, re-seen unchanged Saturday: an unchanged poll writes no
    // row, so nothing newer existed in between.
    expect(staleAtBet("2026-10-10 18:00:00", betAt)).toBe(false);
  });
  it("fails closed on a missing or unreadable time", () => {
    expect(staleAtBet(null, betAt)).toBe(true);
    expect(staleAtBet("not a time", betAt)).toBe(true);
  });
});
