import { describe, expect, it } from "vitest";
import { shortT } from "./movement";

describe("shortT (UTC snapshot text -> ET display)", () => {
  it("converts naive-UTC timestamps to ET (EDT, -4h)", () => {
    expect(shortT("2025-10-13 12:00:00")).toBe("10-13 08:00");
    expect(shortT("2025-10-13 12:00:00.000000")).toBe("10-13 08:00");
  });

  it("converts during EST (-5h) and crosses the date line", () => {
    expect(shortT("2025-12-01 03:30:00")).toBe("11-30 22:30");
  });

  it("accepts ISO 'T' separators", () => {
    expect(shortT("2025-10-13T12:00:00")).toBe("10-13 08:00");
  });

  it("returns unparseable input unchanged", () => {
    expect(shortT("not a timestamp")).toBe("not a timestamp");
    expect(shortT("")).toBe("");
  });
});
