import { expect, test } from "@playwright/test";
import { armPositionsFor } from "./fixture/expected.mjs";
import { seededNow } from "./helpers/fixture";

// Research (2026-10-14, programme step 11): the public record of what is being
// tested. The cards come from the stored Monday read (arm_positions), never a
// recomputation; the honest-leaderboard rules are what these tests pin.

const SEED_NOW = seededNow();

test.describe("research", () => {
  test("one card per registered hypothesis, in slot order, never ranked", async ({
    page,
  }) => {
    await page.goto("/research");
    const cards = page.locator(
      'section[aria-label="The strategies on paper"] article',
    );
    await expect(cards).toHaveCount(7);
    const ids = await cards.evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-hypothesis")),
    );
    expect(ids).toEqual([
      "H-ARM-1HU",
      "H-ARM-1HO",
      "H-ARM-FGU",
      "H-ARM-WX1H",
      "H-ARM-WXFG",
      "H-ARM-HT1H",
      "H-PRICE-HR",
    ]);
    await expect(page.getByText(/#1|leading|winner/)).toHaveCount(0);
  });

  test("each card shows its own standard, the counts, the read date and the next read", async ({
    page,
  }) => {
    await page.goto("/research");
    const rows = armPositionsFor(SEED_NOW);
    const one = page.locator('article[data-hypothesis="H-ARM-1HU"]');
    await expect(one.getByTestId("status")).toHaveText("collecting");
    await expect(one).toContainText(
      "12 of 30 readings · 2 weeks of 3 · 2 excluded · 14 logged",
    );
    await expect(one).toContainText("EV vs close -1.2% (-5.1% to +2.6%)");
    await expect(one).toContainText("run 38590000009");
    await expect(one).toContainText(`Next read ${rows[0].next_read}`);
    await expect(
      one.getByLabel("position between the stop and promote boundaries"),
    ).toBeVisible();
    const pricing = page.locator('article[data-hypothesis="H-PRICE-HR"]');
    await expect(pricing).toContainText("3 of 40 opportunities");
    await expect(pricing.getByTestId("status")).toHaveText("collecting");
  });

  test("not enough data stays a status: no EV below ten readings, outdated past eight days, no row reads not yet read", async ({
    page,
  }) => {
    await page.goto("/research");
    const over = page.locator('article[data-hypothesis="H-ARM-1HO"]');
    await expect(over).toContainText(
      "EV vs close: not enough data (1 of 10 to show one)",
    );
    const pricing = page.locator('article[data-hypothesis="H-PRICE-HR"]');
    await expect(
      pricing.locator(".bv-badge", { hasText: "outdated" }),
    ).toHaveCount(1);
    const ht = page.locator('article[data-hypothesis="H-ARM-HT1H"]');
    await expect(ht.getByTestId("status")).toHaveText("not yet read");
    await expect(ht).toContainText("Not yet read.");
    await expect(
      page.locator('article[data-hypothesis="H-ARM-1HU"] .bv-badge', {
        hasText: "outdated",
      }),
    ).toHaveCount(0);
  });

  test("the exploratory collector sits apart, with no decision bar and the gap rule beside it", async ({
    page,
  }) => {
    await page.goto("/research");
    await expect(
      page.locator(
        'section[aria-label="The strategies on paper"] article[data-hypothesis="H-ARM-EVP"]',
      ),
    ).toHaveCount(0);
    const evp = page.locator(
      'section[aria-label="Exploratory"] article[data-hypothesis="H-ARM-EVP"]',
    );
    await expect(evp).toHaveCount(1);
    await expect(evp).toContainText("exploratory");
    await expect(evp.getByTestId("status")).toHaveText("collecting");
    await expect(evp).toContainText(
      "4 readings · 2 weeks · 1 excluded · 1 pending · 6 logged",
    );
    await expect(evp).toContainText(
      "EV vs close: not enough data (4 of 10 to show one)",
    );
    await expect(evp.getByTestId("comparison")).toContainText(
      "Same weeks, first-half unders by the gap: 11 readings, EV vs close -1.5% (-6.1% to +3.1%). Games both chose: 3; this rule only: 1; the gap only: 8.",
    );
    await expect(evp).toContainText("no error budget");
    await expect(evp.getByRole("progressbar")).toHaveCount(0);
    await expect(
      evp.getByLabel("position between the stop and promote boundaries"),
    ).toHaveCount(0);
  });

  test("explains the judge in plain words with the protocol's numbers, and names the personal stake as never evidence", async ({
    page,
  }) => {
    await page.goto("/research");
    const how = page.locator('section[aria-label="How a strategy is judged"]');
    await expect(how).toContainText("30 readings over 3 weeks");
    await expect(how).toContainText("3% or better");
    await expect(how).toContainText("200 readings");
    await expect(how).toContainText("40 such opportunities");
    await expect(how).toContainText("never evidence for any strategy");
  });

  test("lists the closed hypotheses from the registry with their verdicts", async ({
    page,
  }) => {
    await page.goto("/research");
    const table = page.locator('table[aria-label="Closed hypotheses"]');
    await expect(table.locator("tbody tr")).not.toHaveCount(0);
    await expect(table).toContainText("H-LIT-COX");
    await expect(table).toContainText("tested, no edge");
    await expect(table).toContainText("H-MODEL-FIX");
    await expect(page.locator('section[aria-label="The finding"]')).toHaveCount(
      0,
    );
  });

  test("the glossary is where /glossary lands, with the visitor's ten terms", async ({
    page,
  }) => {
    await page.goto("/research#glossary");
    const glossary = page.locator("section#glossary");
    await expect(glossary).toBeVisible();
    await expect(
      glossary.getByRole("heading", { name: /Terms/ }),
    ).toBeVisible();
    const terms = await glossary.locator("dt").allInnerTexts();
    expect(terms).toEqual([
      "Gap",
      "Our number",
      "Hard Rock line",
      "Market line",
      "Price and fair price",
      "Line value",
      "Unit",
      "Paper pick",
      "Weekly cap",
      "Plausibly",
    ]);
  });

  test("keeps the Board key, links to every game we have rated and names the helpline", async ({
    page,
  }) => {
    await page.goto("/research");
    await expect(
      page.locator('section[aria-label="How to read the Board"]'),
    ).toContainText("Green");
    await expect(
      page.getByRole("link", { name: "Every game we have rated →" }),
    ).toHaveAttribute("href", "/records");
    await expect(page.getByText("1-833-PLAYWISE").first()).toBeVisible();
  });

  test("every page carries the footer's responsible-gambling line", async ({
    page,
  }) => {
    for (const path of ["/", "/results", "/research"]) {
      await page.goto(path);
      await expect(page.locator("footer")).toContainText(
        "Not betting advice. 21+, Florida, Hard Rock Bet. Past results do not predict future results. Gambling problem? 1-833-PLAYWISE.",
      );
    }
  });
});

test.describe("research, signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a visitor reads the same cards and no dollar figure", async ({
    page,
  }) => {
    await page.goto("/research");
    await expect(
      page.locator('section[aria-label="The strategies on paper"] article'),
    ).toHaveCount(7);
    expect(await page.locator("body").innerText()).not.toMatch(/\$\s?\d/);
  });
});
