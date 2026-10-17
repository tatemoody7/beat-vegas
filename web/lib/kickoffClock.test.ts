import { describe, expect, it } from "vitest";
import {
  clockText,
  localKickoffHour,
  tzShiftHours,
  utcOffsetHours,
} from "./kickoffClock";

// The same cases as tests/test_situational.py: the page and the model input
// read one clock.
describe("localKickoffHour", () => {
  it("Michigan 19:30Z is 3:30pm local, not ~1pm", () => {
    expect(localKickoffHour("2026-10-17T19:30:00Z", "America/Detroit")).toBe(
      15.5,
    );
  });
  it("a Mountain-time venue", () => {
    expect(localKickoffHour("2026-10-17T20:00:00Z", "America/Denver")).toBe(14);
  });
  it("each side of the 2026-11-01 DST change", () => {
    expect(localKickoffHour("2026-10-31T19:30:00Z", "America/Detroit")).toBe(
      15.5,
    );
    expect(localKickoffHour("2026-11-07T19:30:00Z", "America/Detroit")).toBe(
      14.5,
    );
  });
  it("Arizona keeps MST all season", () => {
    expect(localKickoffHour("2026-10-31T19:30:00Z", "America/Phoenix")).toBe(
      12.5,
    );
    expect(localKickoffHour("2026-11-07T19:30:00Z", "America/Phoenix")).toBe(
      12.5,
    );
  });
  it("no zone or a bad one is null, never a guess", () => {
    expect(localKickoffHour("2026-10-17T19:30:00Z", null)).toBeNull();
    expect(localKickoffHour("2026-10-17T19:30:00Z", "Not/AZone")).toBeNull();
    expect(localKickoffHour(null, "America/Detroit")).toBeNull();
  });
});

describe("tzShiftHours", () => {
  const k = "2026-10-17T19:30:00Z";
  it("whole hours, east positive", () => {
    expect(
      tzShiftHours({
        kickoff: k,
        venueTz: "America/Detroit",
        awayHomeTz: "America/New_York",
      }),
    ).toBe(0);
    expect(
      tzShiftHours({
        kickoff: k,
        venueTz: "America/New_York",
        awayHomeTz: "America/Los_Angeles",
      }),
    ).toBe(3);
    expect(
      tzShiftHours({
        kickoff: k,
        venueTz: "America/Chicago",
        awayHomeTz: "America/New_York",
      }),
    ).toBe(-1);
  });
  it("a Phoenix visitor at Denver: one hour before Nov 1, none after", () => {
    const z = { venueTz: "America/Denver", awayHomeTz: "America/Phoenix" };
    expect(tzShiftHours({ ...z, kickoff: "2026-10-31T19:00:00Z" })).toBe(1);
    expect(tzShiftHours({ ...z, kickoff: "2026-11-07T19:00:00Z" })).toBe(0);
  });
  it("null when either zone is unknown", () => {
    expect(
      tzShiftHours({
        kickoff: k,
        venueTz: "America/Detroit",
        awayHomeTz: null,
      }),
    ).toBeNull();
  });
  it("offsets", () => {
    expect(utcOffsetHours(k, "America/New_York")).toBe(-4);
    expect(utcOffsetHours(k, "America/Phoenix")).toBe(-7);
  });
});

describe("clockText", () => {
  it("formats like situational.clock_text", () => {
    expect(clockText(15.5)).toBe("3:30pm");
    expect(clockText(12)).toBe("12:00pm");
    expect(clockText(0.25)).toBe("12:15am");
    expect(clockText(19)).toBe("7:00pm");
    expect(clockText(null)).toBeNull();
  });
});
