import { expect, test } from "@playwright/test";
import { BOARD_KEY, BOARD_KEY_SHORTLIST } from "../lib/boardKey";
import {
  EV_CAVEAT,
  FEED_NOTE,
  NOTHING_POTENTIAL,
  SHORTLIST_HEAD,
} from "../lib/shortlist";
import { SHORTLIST_IDS } from "./fixture/expected.mjs";
import { fixture } from "./helpers/fixture";

// The Research top 10 (H-1H-SHORTLIST, website plan PR E): the frozen
// publication above the Board, labelled apart from the Board's rank, and each
// shortlisted game's full analysis at the top of its page, frozen beside the
// latest Hard Rock price. Research wording only, signed in or out.

const { byId } = fixture();
const [R1, , R3] = SHORTLIST_IDS;

test.describe("the research top 10", () => {
  test("sits above the Board in research rank order, labelled apart from the Board's rank", async ({
    page,
  }) => {
    await page.goto("/");
    const list = page.locator('section[aria-label="Research top 10"]');
    await expect(list.locator("h2")).toHaveText(SHORTLIST_HEAD);
    const links = list.locator("a[data-research-rank]");
    await expect(links).toHaveCount(3);
    for (const [i, id] of SHORTLIST_IDS.entries()) {
      const a = links.nth(i);
      await expect(a).toHaveAttribute("href", `/game/${id}`);
      await expect(a).toContainText(`R${i + 1}`);
      const g = byId.get(id)!;
      await expect(a).toContainText(`${g.away} @ ${g.home}`);
    }
    await expect(links.nth(0)).toContainText(
      "estimated EV +1.8% (rough range 0.0% to +3.9%)",
    );
    await expect(links.nth(0)).toContainText("Fair price");
    await expect(links.nth(2)).toContainText(
      "no estimate (incomplete pricing)",
    );
    await expect(links.nth(2)).toContainText("Insufficient pricing data");
    // No entry reaches potential value, and the page says so.
    await expect(list).toContainText(NOTHING_POTENTIAL);
    await expect(list).toContainText(`${EV_CAVEAT} ${FEED_NOTE}`);
    await expect(list).toContainText("frozen, never re-ranked");
    // It sits above the Board heading; the key points to it.
    const listBox = await list.boundingBox();
    const heading = await page.locator("h1.bv-page-title").boundingBox();
    expect(listBox!.y).toBeLessThan(heading!.y);
    await expect(
      page.locator('p[aria-label="How to read the Board"]'),
    ).toContainText(`${BOARD_KEY} ${BOARD_KEY_SHORTLIST}`);
  });

  test("a shortlisted game opens with its full analysis: frozen beside the latest price", async ({
    page,
  }) => {
    await page.goto(`/game/${R1}`);
    const sec = page.locator('section[aria-label="Research shortlist"]');
    await expect(sec.locator("h2")).toHaveText(
      "Research shortlist R1 — research ranking, not the Board's rank",
    );
    const frozen = sec.getByTestId("frozen");
    await expect(frozen).toContainText("(frozen)");
    await expect(frozen).toContainText("u44.5 +100");
    await expect(frozen).toContainText(
      "estimated EV +1.8% (rough range 0.0% to +3.9%)",
    );
    await expect(frozen).toContainText("Fair price");
    await expect(frozen).toContainText("5 reference books in the same sweep");
    await expect(sec.getByTestId("latest")).toContainText(
      "Latest Hard Rock price",
    );
    await expect(sec.getByTestId("why")).toHaveText(
      /^R1: estimated EV \+1\.8%/,
    );
    // The matchup speaks of scoring, with each stat's percentile and verdict.
    const stats = sec.locator('ul[aria-label="Matchup stats"]');
    await expect(stats).toContainText("21st percentile");
    await expect(stats).toContainText("points to less scoring");
    await expect(stats).toContainText("not shown to beat the line");
    await expect(sec).toContainText("visitors travel ~435 miles");
    await expect(sec).toContainText("~19:30 local");
    await expect(sec).not.toContainText("the under");
    // The Board's own rank is named as a different ranking.
    await expect(sec).toContainText("On the Board this game is #");
    await expect(page.getByTestId("board-rank-label")).toHaveText("Board");
    // The analysis comes before the decision card.
    const secBox = await sec.boundingBox();
    const decision = await page
      .locator("section.bv-card", { hasText: "The decision" })
      .boundingBox();
    expect(secBox!.y).toBeLessThan(decision!.y);
  });

  test("an informational candidate says why it has no estimate", async ({
    page,
  }) => {
    await page.goto(`/game/${R3}`);
    const frozen = page
      .locator('section[aria-label="Research shortlist"]')
      .getByTestId("frozen");
    await expect(frozen).toContainText("no estimate (incomplete pricing)");
    await expect(frozen).toContainText(
      "Incomplete pricing: insufficient pricing data (2 reference books in the same sweep).",
    );
  });

  test("a game off the list has no research section", async ({ page }) => {
    const off = [...byId.values()].find(
      (g) => !SHORTLIST_IDS.includes(g.id) && g.kick.getTime() > Date.now(),
    )!;
    await page.goto(`/game/${off.id}`);
    await expect(
      page.locator('section[aria-label="Research shortlist"]'),
    ).toHaveCount(0);
  });
});

test.describe("the research top 10, signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a visitor sees the list and the analysis before kickoff, in research wording", async ({
    page,
  }) => {
    await page.goto("/");
    const list = page.locator('section[aria-label="Research top 10"]');
    await expect(list.locator("a[data-research-rank]")).toHaveCount(3);
    await expect(list).not.toContainText(/\bbet\b/i);
    await page.goto(`/game/${R1}`);
    const sec = page.locator('section[aria-label="Research shortlist"]');
    await expect(sec).toBeVisible();
    await expect(sec).not.toContainText(/\bbet\b|bet one unit|proven/i);
  });
});
