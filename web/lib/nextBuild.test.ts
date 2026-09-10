import { describe, expect, it } from "vitest";
import { cardBuilds, nextBuild } from "@/lib/nextBuild";

// ET instants. September 2026 is EDT (UTC-4), so 20:00Z is 16:00 ET.
const et = (iso: string) => new Date(iso);

describe("cardBuilds", () => {
  it("finds the four card slots and leaves grading out", () => {
    const days = cardBuilds().map((s) => s.day);
    expect(days.sort()).toEqual(["Fri", "Sat", "Thu", "Tue"]);
  });
});

describe("nextBuild", () => {
  it("names the next afternoon slot later the same week", () => {
    // Wed 2026-09-09, 18:00Z = 14:00 ET → Thursday afternoon is next.
    expect(nextBuild(et("2026-09-09T18:00:00Z"))?.label).toBe(
      "Thu 3:45–5:15pm ET",
    );
  });

  it("treats a slot still inside its window as the next one", () => {
    // Thu 16:00 ET is inside the 15:45–17:15 window: it has not landed yet.
    expect(nextBuild(et("2026-09-10T20:00:00Z"))?.label).toBe(
      "Thu 3:45–5:15pm ET",
    );
  });

  it("moves on once a slot's window has closed", () => {
    // Thu 17:30 ET is past the close → Friday.
    expect(nextBuild(et("2026-09-10T21:30:00Z"))?.label).toBe(
      "Fri 3:45–5:15pm ET",
    );
  });

  it("labels the Saturday morning window with a single am suffix", () => {
    // Fri 18:00 ET, past Friday's close → Saturday morning.
    expect(nextBuild(et("2026-09-11T22:00:00Z"))?.label).toBe(
      "Sat 7:00–8:15am ET",
    );
  });

  it("wraps from Saturday afternoon round to Tuesday", () => {
    // Sat 14:00 ET, past the morning window → Tuesday.
    expect(nextBuild(et("2026-09-12T18:00:00Z"))?.label).toBe(
      "Tue 3:45–5:15pm ET",
    );
  });
});
