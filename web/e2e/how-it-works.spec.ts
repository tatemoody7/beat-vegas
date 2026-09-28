import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";

// /how-it-works (app/how-it-works/page.tsx), 2026-09-28: the page a visitor
// reads after the Board. The prose sections, the 2023–25 backtest headed as a
// backtest (the post-mortem's `dimension='all'` bucket for hist_2023_25,
// fbs_only, real, cap5), the gap ladder, the one uncapped record row, the nine
// terms, the records link and the helpline. The live-season panel, the flags
// and the method fold render only behind the cookie.
//
// The bucket numbers below are the ones seed.mjs writes (fixtureRows); the
// arithmetic is lib/record.ts::recordFromCounts.

const { week } = fixture();

// (hist_2023_25, fbs_only, real, cap5, all): 102 unders, 66 overs, 1 push, +26.9u.
const CAP5 = { unders: 102, overs: 66, pushes: 1, units: 26.9 };
const cap5Hit = `${((100 * CAP5.unders) / (CAP5.unders + CAP5.overs)).toFixed(1)}%`;
const cap5N = CAP5.unders + CAP5.overs + CAP5.pushes;
const cap5Roi = `${((100 * CAP5.units) / cap5N).toFixed(1)}%`;
// (hist_2023_25, fbs_only, real, gap175, all): 285-230-5.
const GAP175 = { unders: 285, overs: 230, pushes: 5 };
const gap175Hit = `${((100 * GAP175.unders) / (GAP175.unders + GAP175.overs)).toFixed(1)}%`;
const LADDER_BUCKETS = ["<0", "0–1.75", "1.75–3", "3–5", "5+"];

test.describe("how it works", () => {
  test("says what this is, how to read the Board and where bets are priced", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    await expect(page.locator("h1.bv-page-title")).toHaveText("How it works");
    await expect(
      page.locator('section[aria-label="What this is"]'),
    ).toContainText(
      "Beat Vegas rates one bet: the college football first-half under.",
    );
    const keys = page.locator('section[aria-label="How to read the Board"]');
    await expect(keys.locator("li")).toHaveCount(3);
    await expect(keys).toContainText("Green — bet one unit.");
    await expect(keys).toContainText("Amber, “Not yet”");
    await expect(keys).toContainText("Red, “Pass”");
    await expect(keys).toContainText(
      "Best time to look: Friday after 5:30pm ET",
    );
    await expect(
      page.locator('section[aria-label="Where bets are priced"]'),
    ).toContainText("Hard Rock Bet, the only sportsbook in Florida.");
  });

  test("the backtest is headed as a backtest and carries the cap-5 record", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    const finding = page.locator('section[aria-label="The finding"]');
    await expect(finding).toContainText(
      "Backtest, 2023–25 (not money bet) · first-half unders, 5 a week",
    );
    await expect(finding.locator("p.text-6xl")).toHaveText(cap5Hit);
    await expect(finding).toContainText(
      `${CAP5.unders}-${CAP5.overs}-${CAP5.pushes}P · +${CAP5.units.toFixed(2)}u · ROI +${cap5Roi}`,
    );
    await expect(finding).toContainText(
      new RegExp(
        `${cap5N} bets, could plausibly be \\d+%–\\d+%\\. Hard Rock did not exist in these seasons\\. This is what the method would have returned, not money won\\.`,
      ),
    );
    // Nothing on the page reads as a live win rate: no "Without the cap"
    // sentence, no 2026 row beside a 9-6 ledger.
    await expect(finding).not.toContainText("Without the cap");
  });

  test("the gap ladder draws one bar per band and the break-even line", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    const chart = page.locator(
      'section[aria-label="The finding"] .recharts-wrapper',
    );
    await expect(chart).toBeVisible();
    const bars = chart.locator(".recharts-bar-rectangle");
    await expect(bars).toHaveCount(LADDER_BUCKETS.length);
    expect(LADDER_BUCKETS.length).toBeGreaterThanOrEqual(4);
    // Every bar is drawn (Recharts 3 needs isAnimationActive={false} or the
    // rectangles stay at height 0 -- the bug the CLAUDE.md gotcha records).
    const heights = await bars
      .locator("path, rect")
      .evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height));
    for (const h of heights) expect(h).toBeGreaterThan(0);
    for (const b of LADDER_BUCKETS) await expect(chart).toContainText(b);
    await expect(chart.locator(".recharts-reference-line line")).toHaveCount(1);
    await expect(chart.getByText("52.4% break-even")).toBeVisible();
  });

  test("the real-close records table is the one uncapped row", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    const rows = page
      .locator('table[aria-label="Records at real closing lines"]')
      .locator("tbody tr");
    await expect(rows).toHaveCount(1);
    await expect(rows.nth(0)).toContainText("2023–25, every gap 1.75+");
    await expect(rows.nth(0)).toContainText(gap175Hit);
    await expect(rows.nth(0)).toContainText(/\d+%–\d+%$/);
  });

  test("the glossary is where /glossary lands, with the visitor's ten terms", async ({
    page,
  }) => {
    await page.goto("/how-it-works#glossary");
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

  test("links to every game we have rated and names the helpline", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    await expect(
      page.getByRole("link", { name: "Every game we have rated →" }),
    ).toHaveAttribute("href", "/records");
    await expect(page.getByText(/call 1-800-GAMBLER/)).toBeVisible();
  });

  test("signed in, the live season panel, the flags and the method fold follow", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    const research = page.locator('section[aria-label="Research, signed in"]');
    await expect(research).toBeVisible();
    const head = research.getByRole("heading", {
      name: `${week.season} so far`,
    });
    await expect(head).toContainText("106 of 190 rated games graded · 10 bets");
    const panel = research
      .locator("dl")
      .filter({ hasText: "Average miss, points" });
    await expect(panel).toContainText("Hard Rock’s line8.7");
    await expect(panel).toContainText("HR at market28-32-1P · 29-31-1P");
    await expect(
      research.getByText(/Eleven statements are judged on this page/),
    ).toBeVisible();
    await expect(research.getByText("holds up", { exact: true })).toBeVisible();
    const fold = research
      .locator("details")
      .filter({ hasText: "Method and sanity checks" });
    await expect(fold).not.toHaveAttribute("open", "");
    await fold.locator("summary").click();
    await expect(fold).toHaveAttribute("open", "");
    await expect(
      fold.locator('table[aria-label="Records at an estimated line"] tbody tr'),
    ).toHaveCount(2);
    // No --good / --bad anywhere below the estimated heading: colour is the
    // grade language and an estimated line is not a grade.
    const coloured = await fold.evaluate((d) =>
      [...d.querySelectorAll<HTMLElement>("td, span, p")]
        .map((el) => el.getAttribute("style") ?? "")
        .filter((s) => /--good|--bad/.test(s)),
    );
    expect(coloured).toEqual([]);
    await expect(fold).toContainText("Overall1934-0.12");
  });
});

test.describe("how it works, signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("a visitor reads the page without the research section", async ({
    page,
  }) => {
    await page.goto("/how-it-works");
    await expect(
      page.locator('section[aria-label="The finding"]'),
    ).toBeVisible();
    await expect(
      page.locator('section[aria-label="Research, signed in"]'),
    ).toHaveCount(0);
    await expect(page.getByText("What to change")).toHaveCount(0);
    await expect(page.getByText("Method and sanity checks")).toHaveCount(0);
  });
});
