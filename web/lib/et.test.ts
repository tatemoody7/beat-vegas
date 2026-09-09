import { describe, expect, it } from "vitest";

import { ET_ZONE, etClock12, etDay, etMinutesOfDay, etParts, pad2 } from "./et";

describe("etParts", () => {
  it("names the zone the whole site runs on", () => {
    expect(ET_ZONE).toBe("America/New_York");
  });

  it("reads EDT (-4h): Tue Sep 15 2026 13:15Z is 9:15am ET", () => {
    expect(etParts(new Date("2026-09-15T13:15:00Z"))).toEqual({
      weekday: "Tue",
      year: 2026,
      month: 9,
      day: 15,
      hour: 9,
      minute: 15,
    });
  });

  it("reads EST (-5h): Tue Nov 17 2026 14:15Z is 9:15am ET", () => {
    expect(etParts(new Date("2026-11-17T14:15:00Z"))).toMatchObject({
      weekday: "Tue",
      day: 17,
      hour: 9,
      minute: 15,
    });
  });

  it("midnight is hour 0 (h23), and the ET day rolls at 04:00Z in EDT", () => {
    const p = etParts(new Date("2026-09-11T04:00:00Z"));
    expect(p.hour).toBe(0);
    expect(p.minute).toBe(0);
    expect(p.day).toBe(11);
    expect(p.weekday).toBe("Fri");
    // One minute earlier is still Thursday the 10th, 11:59pm.
    expect(etParts(new Date("2026-09-11T03:59:00Z"))).toMatchObject({
      weekday: "Thu",
      day: 10,
      hour: 23,
      minute: 59,
    });
  });
});

describe("etDay / etMinutesOfDay", () => {
  it("formats the ET calendar day", () => {
    expect(etDay(new Date("2026-09-12T16:00:00Z"))).toBe("2026-09-12");
    // 02:00Z Sep 13 is still Sep 12 in ET.
    expect(etDay(new Date("2026-09-13T02:00:00Z"))).toBe("2026-09-12");
    expect(etDay(new Date("2026-12-01T03:30:00Z"))).toBe("2026-11-30");
  });

  it("counts minutes since ET midnight in both DST regimes", () => {
    expect(etMinutesOfDay(new Date("2026-09-15T13:15:00Z"))).toBe(9 * 60 + 15);
    expect(etMinutesOfDay(new Date("2026-11-17T14:15:00Z"))).toBe(9 * 60 + 15);
    expect(etMinutesOfDay(new Date("2026-09-11T04:00:00Z"))).toBe(0);
    expect(etMinutesOfDay(new Date("2026-09-11T03:59:00Z"))).toBe(23 * 60 + 59);
  });
});

describe("etClock12", () => {
  it("renders the card's built time: Fri Sep 11 2026 22:07Z is Fri 6:07pm ET", () => {
    expect(etClock12(new Date("2026-09-11T22:07:00Z"))).toBe("Fri 6:07pm");
  });

  it("renders a kickoff with the short suffixes: Sat 7:30p", () => {
    expect(etClock12(new Date("2026-09-12T23:30:00Z"), ["a", "p"])).toBe(
      "Sat 7:30p",
    );
  });

  it("reads 12, never 0, at midnight and noon ET", () => {
    // EDT: 04:00Z = 12:00am ET, 16:00Z = 12:00pm ET
    expect(etClock12(new Date("2026-09-12T04:00:00Z"))).toBe("Sat 12:00am");
    expect(etClock12(new Date("2026-09-12T16:05:00Z"))).toBe("Sat 12:05pm");
  });

  it("follows the DST change: Sat Nov 21 2026 00:30Z is Fri 7:30pm EST", () => {
    expect(etClock12(new Date("2026-11-21T00:30:00Z"), ["a", "p"])).toBe(
      "Fri 7:30p",
    );
  });
});

describe("pad2", () => {
  it("zero-pads a single digit and leaves two digits alone", () => {
    expect(pad2(7)).toBe("07");
    expect(pad2(12)).toBe("12");
  });
});
