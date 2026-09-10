import { describe, expect, it } from "vitest";
import { distinctTag } from "@/lib/labels";

// The board and the game page both render a blocker tag next to the action
// line, and both are built from the same blocker — so the tag has to be
// suppressed when it would just say the sentence again.

describe("distinctTag", () => {
  it("drops a tag the action line already says", () => {
    expect(
      distinctTag(
        "Not yet — Hard Rock's price is -125; needs -110 or better",
        "Not yet — Hard Rock’s price is -125; needs -110 or better.",
      ),
    ).toBeNull();
  });

  it("ignores curly apostrophes and trailing punctuation", () => {
    expect(
      distinctTag("Hard Rock’s price is -125", "hard rock's price is -125!"),
    ).toBeNull();
  });

  it("keeps a tag that adds something", () => {
    const tag = "Hard Rock has no first-half line";
    expect(distinctTag(tag, "It becomes a bet at under 26.0 or higher.")).toBe(
      tag,
    );
  });

  it("passes null and empty tags straight through as null", () => {
    expect(distinctTag(null, "anything")).toBeNull();
    expect(distinctTag("   ", "anything")).toBeNull();
  });

  it("keeps the tag when there is no action line to compare against", () => {
    expect(distinctTag("past the 5-bet cap", null)).toBe("past the 5-bet cap");
  });
});
