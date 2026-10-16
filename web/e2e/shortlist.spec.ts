import { expect, test } from "@playwright/test";
import { SHORTLIST_IDS } from "./fixture/expected.mjs";
import { fixture } from "./helpers/fixture";

// The Board's top-10 analysis (H-1H-SHORTLIST; Tate 2026-10-16): no separate
// list on the Board; each of the Board's #1-#10 opens its game page with the
// analysis the newest scheduled card saved, beside Hard Rock's price now. A
// game past #10 shows none, even when the card saved one for it.

const { expected } = fixture();
const rank = new Map(expected.rankOrder.map((id, i) => [id, i + 1]));
const [FIRST, , THIRD] = SHORTLIST_IDS;
const ELEVENTH = expected.rankOrder[10];

test.describe("the Board's top-10 analysis", () => {
  test("the Board has no separate research list", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.locator('section[aria-label="Research top 10"]'),
    ).toHaveCount(0);
    await expect(page.getByText(/Research top 10|R1\b/)).toHaveCount(0);
  });

  test("a top-10 game opens with its analysis, headed by its Board rank", async ({
    page,
  }) => {
    expect(rank.get(FIRST)!).toBeLessThanOrEqual(10);
    await page.goto(`/game/${FIRST}`);
    const sec = page.locator('section[aria-label="Analysis"]');
    await expect(sec.locator("h2")).toHaveText(
      `Analysis — Board #${rank.get(FIRST)}`,
    );
    const atCard = sec.getByTestId("frozen");
    await expect(atCard).toContainText(/At the \w{3} \d{1,2}:\d\d[ap]m card/);
    await expect(atCard).toContainText("u44.5 +100");
    await expect(atCard).toContainText(
      "estimated EV +1.8% (rough range 0.0% to +3.9%)",
    );
    await expect(atCard).toContainText("Fair price");
    await expect(sec.getByTestId("latest")).toContainText("Hard Rock now");
    const stats = sec.locator('ul[aria-label="Matchup stats"]');
    await expect(stats).toContainText("21st percentile");
    await expect(stats).toContainText("points to less scoring");
    await expect(sec).toContainText("visitors travel ~435 miles");
    await expect(sec).not.toContainText("the under");
    // No second ranking and no fine print.
    await expect(sec).not.toContainText(
      /research ranking|R\d|not proof of profit|Feed quote/,
    );
    // The analysis comes before the decision card.
    const secBox = await sec.boundingBox();
    const decision = await page
      .locator("section.bv-card", { hasText: "The decision" })
      .boundingBox();
    expect(secBox!.y).toBeLessThan(decision!.y);
  });

  test("a game without a price says so instead of an estimate", async ({
    page,
  }) => {
    await page.goto(`/game/${THIRD}`);
    const atCard = page
      .locator('section[aria-label="Analysis"]')
      .getByTestId("frozen");
    await expect(atCard).toContainText("no estimate (incomplete pricing)");
    await expect(atCard).toContainText(
      "Incomplete pricing: insufficient pricing data (2 reference books in the same sweep).",
    );
  });

  test("a game past #10 shows no analysis, even when the card saved one", async ({
    page,
  }) => {
    test.skip(
      ELEVENTH === undefined,
      "the fixture week has fewer than 11 ranked games",
    );
    await page.goto(`/game/${ELEVENTH}`);
    await expect(page.locator('section[aria-label="Analysis"]')).toHaveCount(0);
  });
});

test.describe("the Board's top-10 analysis, signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a visitor sees the analysis before kickoff, with no bet language", async ({
    page,
  }) => {
    await page.goto(`/game/${FIRST}`);
    const sec = page.locator('section[aria-label="Analysis"]');
    await expect(sec).toBeVisible();
    await expect(sec).not.toContainText(/\bbet\b|bet one unit|proven/i);
  });
});
