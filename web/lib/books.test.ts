import { describe, expect, it } from "vitest";
import { bookLabel, isExchange, isSynthetic, titleCase } from "./books";

describe("book labels", () => {
  it("known keys get their friendly label, any casing", () => {
    expect(bookLabel("hardrockbet")).toBe("Hard Rock");
    expect(bookLabel("DraftKings")).toBe("DraftKings");
  });
  it("unknown keys are title-cased, never the raw key", () => {
    expect(bookLabel("some_new_book")).toBe("Some New Book");
    expect(bookLabel("pinnacle")).toBe("Pinnacle");
    expect(titleCase("a-b")).toBe("A B");
  });
  it("classifies exchanges and the CFBD synthetic consensus", () => {
    expect(isExchange("Kalshi")).toBe(true);
    expect(isSynthetic("consensus")).toBe(true);
    expect(isSynthetic("Consensus")).toBe(true);
    expect(isSynthetic("draftkings")).toBe(false);
  });
});
