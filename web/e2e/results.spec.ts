import { expect, test } from "@playwright/test";
import { PRICING_OPPORTUNITY } from "./fixture/expected.mjs";
import { fixture } from "./helpers/fixture";

// /results is RECORD (final-2026 plan, D16, 2026-10-18; the path stays): the
// arms' forward picks with the judge's reading first, then the pricing study's
// forward opportunities, then the season comparison without a personal-stake
// row. The bet ledger, the units curve, the picks table, the week picker and
// the bet CSV left with the owner's log path (D2); the 30 real tickets stay in
// the database and appear only in the final report. Every record here is
// worked out from the fixture rows, not typed in.

const { week, expected } = fixture();
const L = expected.ledger;

/** lib/record.ts::recordFrom on a list of under/over outcomes and units. */
function record(rows: { under: boolean; units: number }[]) {
  const wins = rows.filter((r) => r.under).length;
  const units = rows.reduce((a, r) => a + r.units, 0);
  return {
    record: `${wins}-${rows.length - wins}`,
    hit: `${((100 * wins) / rows.length).toFixed(1)}%`,
    units: `${units >= 0 ? "+" : ""}${units.toFixed(2)}`,
  };
}
const unitFor = (under: boolean) =>
  under ? Math.round((100 / 110) * 100) / 100 : -1;

const played = week.games.filter((g) => g.played !== null);
const marketFirstHalf = record(
  played.map((g) => {
    const fh = g.played!.homeFh + g.played!.awayFh;
    const close = g.hr![g.hr!.length - 1].line;
    return { under: fh < close, units: unitFor(fh < close) };
  }),
);
const marketFullGame = record(
  played.map((g) => {
    const pts = g.played!.homePts + g.played!.awayPts;
    return { under: pts < g.fg.total, units: unitFor(pts < g.fg.total) };
  }),
);

test.describe("record", () => {
  test("is headed Record and runs arms, then pricing, then the season comparison, with no ledger", async ({
    page,
  }) => {
    await page.goto("/results");
    await expect(page.locator("h1.bv-page-title")).toHaveText("Record");
    await expect(page.locator(".bv-page-sub")).toHaveText(
      `${week.season} season`,
    );
    await expect(page.locator("nav a[aria-current='page']")).toHaveText(
      "Record",
    );
    // The order down the page: arms, pricing, season comparison.
    const arms = await page
      .locator('section[aria-label="Paper strategies, forward picks"]')
      .boundingBox();
    const pricing = await page
      .locator('section[aria-label="Hard Rock pricing, forward opportunities"]')
      .boundingBox();
    const season = await page
      .locator('table[aria-label="Season summary"]')
      .boundingBox();
    expect(arms!.y).toBeLessThan(pricing!.y);
    expect(pricing!.y).toBeLessThan(season!.y);
    // No ledger, no curve, no picks table, no week picker, no bet CSV.
    await expect(page.locator('section[aria-label="Every bet"]')).toHaveCount(
      0,
    );
    await expect(page.locator(".recharts-wrapper")).toHaveCount(0);
    await expect(page.getByRole("tablist")).toHaveCount(0);
    await expect(page.getByText("Personal stake")).toHaveCount(0);
    await expect(page.getByText("Your picks")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /edit|delete|details/ }),
    ).toHaveCount(0);
    await expect(page.locator('a[href^="/api/bets"]')).toHaveCount(0);
    await expect(page.getByRole("combobox", { name: /week/i })).toHaveCount(0);
    // No dollars are public.
    expect(await page.locator("body").innerText()).not.toMatch(/\$\s?\d/);
  });

  test("the season comparison: market research, the paper rule and the full game; no personal stake", async ({
    page,
  }) => {
    await page.goto("/results");
    const table = page.locator('table[aria-label="Season summary"]');
    // Three rows since 2026-10-18: the Personal stake row left with the ledger
    // (D16); the full-game market row, once the owner's, shows for everyone.
    await expect(table.locator("tbody tr")).toHaveCount(3);
    const rowText = async (label: string) =>
      (
        await table.locator("tr", { hasText: label }).first().innerText()
      ).replace(/\s+/g, " ");
    // Market Research (fact-check audit 2026-10-17): a record with no units or
    // ROI -- no one can bet the consensus.
    const market = await rowText(
      "Market research: every first-half under at the consensus close",
    );
    expect(market).toContain(
      `${marketFirstHalf.hit} ${marketFirstHalf.record} —`,
    );
    expect(market).not.toContain(marketFirstHalf.units);
    expect(
      await rowText("Every game that cleared the bar, on paper"),
    ).toContain(`${L.paper.hit} ${L.paper.record} ${L.paper.units}`);
    await expect(
      table.locator("tr", { hasText: "Personal stake" }),
    ).toHaveCount(0);
    await expect(table.locator("tr", { hasText: "Model" })).toHaveCount(0);
    expect(await rowText("Market — full game")).toContain(
      `${marketFullGame.hit} ${marketFullGame.record} ${marketFullGame.units}`,
    );
  });

  test("the forward picks of every arm, each with its value or the reason it has none; development never listed", async ({
    page,
  }) => {
    await page.goto("/results");
    const sec = page.locator(
      'section[aria-label="Paper strategies, forward picks"]',
    );
    const over = sec.locator('[data-arm="H-ARM-1HO"]');
    await expect(over.locator("h3")).toHaveText(
      "First-half overs · 2 graded · 1 read · 1 excluded",
    );
    await expect(over).toContainText("+3.1%");
    await expect(over).toContainText(
      "excluded: the close sat too far from this line",
    );
    await expect(over).not.toContainText("+50.0%"); // the development row
    const fg = sec.locator('[data-arm="H-ARM-FGU"]');
    await expect(fg).toContainText("FG under 48.5");
    await expect(fg).toContainText("-2.2%");
    await expect(sec.locator('[data-arm="H-ARM-HT1H"] h3')).toHaveText(
      "High totals, first-half unders · 0 graded · 0 read · 0 excluded",
    );
  });

  test("the pricing study's forward opportunities come from the stored Monday row", async ({
    page,
  }) => {
    await page.goto("/results");
    const sec = page.locator(
      'section[aria-label="Hard Rock pricing, forward opportunities"]',
    );
    const rows = sec.locator("tbody tr");
    await expect(rows).toHaveCount(1);
    await expect(rows.first()).toContainText(PRICING_OPPORTUNITY.game);
    await expect(rows.first()).toContainText("+2.9%");
    await expect(rows.first()).toContainText("one feed observation");
  });

  test("the season comparison carries the Wilson interval on every win rate", async ({
    page,
  }) => {
    await page.goto("/results");
    const table = page.locator('table[aria-label="Season summary"]');
    await expect(
      table.getByRole("columnheader", { name: "Plausibly" }),
    ).toBeVisible();
  });
});
