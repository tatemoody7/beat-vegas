import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";

// /proof (app/proof/page.tsx), Concept A "One finding": the headline record
// is the post-mortem's `dimension='all'` bucket for (hist_2023_25, fbs_only,
// real, cap5); the gap ladder is a Recharts bar chart with the break-even line
// drawn; the live season is one panel; everything graded against an estimated
// line sits behind one fold and renders NEUTRAL -- never --good or --bad.
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

test.describe("track record", () => {
  test("the headline is the cap-5 record at real closing lines", async ({
    page,
  }) => {
    await page.goto("/proof");
    await expect(page.locator("h1.bv-page-title")).toHaveText("Track record");
    await expect(page.locator(".bv-page-sub")).toHaveText(
      `2023–25 at real closing lines, plus ${week.season} at Hard Rock’s number.`,
    );
    const finding = page.locator('section[aria-label="The finding"]');
    await expect(finding).toContainText(
      "First-half unders won, 2023–25, 5 a week",
    );
    await expect(finding.locator("p.text-6xl")).toHaveText(cap5Hit);
    await expect(finding).toContainText(
      `${CAP5.unders}-${CAP5.overs}-${CAP5.pushes}P · +${CAP5.units.toFixed(2)}u · ROI +${cap5Roi}`,
    );
    await expect(finding).toContainText(
      new RegExp(`${cap5N} bets, plausibly \\d+\\.\\d%–\\d+\\.\\d%\\.`),
    );
    await expect(finding).toContainText(
      `Without the cap — every game the rule qualified — it won ${gap175Hit} of ${GAP175.unders + GAP175.overs + GAP175.pushes}`,
    );
    await expect(finding).toContainText(
      /Break-even at −110 is 52\.4%, which is (inside|outside) that range\./,
    );
  });

  test("the gap ladder draws one bar per band and the break-even line", async ({
    page,
  }) => {
    await page.goto("/proof");
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
    // The dashed break-even rule and its label (Recharts draws the label in
    // its own layer, so the text is asserted on the chart, not the line).
    await expect(chart.locator(".recharts-reference-line line")).toHaveCount(1);
    await expect(chart.getByText("52.4% break-even")).toBeVisible();
  });

  test("the real-close records table and its intervals", async ({ page }) => {
    await page.goto("/proof");
    const table = page.locator(
      'table[aria-label="Records at real closing lines"]',
    );
    const rows = table.locator("tbody tr");
    await expect(rows).toHaveCount(4);
    await expect(rows.nth(0)).toContainText("2023–25, every gap 1.75+");
    await expect(rows.nth(0)).toContainText(gap175Hit);
    await expect(rows.nth(0)).toContainText(/\d+%–\d+%$/);
    await expect(rows.nth(1)).toContainText(
      `${week.season}, bets at Hard Rock’s line`,
    );
    await expect(rows.nth(1)).toContainText("60.0%");
    await expect(rows.nth(1)).toContainText("too few"); // 10 decided < 30
    await expect(rows.nth(3)).toContainText(
      `${week.season}, every Hard Rock number`,
    );
  });

  test("the live season is one panel named after its scope", async ({
    page,
  }) => {
    await page.goto("/proof");
    const head = page.getByRole("heading", { name: `${week.season} so far` });
    await expect(head).toBeVisible();
    await expect(head).toContainText("106 of 190 rated games graded · 10 bets");
    const panel = page
      .locator("dl")
      .filter({ hasText: "Average miss, points" });
    await expect(panel).toContainText("Hard Rock’s line8.7");
    await expect(panel).toContainText("The market line8.6");
    await expect(panel).toContainText("Our reference line9.9");
    await expect(panel).toContainText("Actual first-half share0.531");
    await expect(panel).toContainText("Better than fair12 of 26");
    await expect(panel).toContainText("HR at market28-32-1P · 29-31-1P");
  });

  test("what to change: the flags, with the watched ones folded", async ({
    page,
  }) => {
    await page.goto("/proof");
    await expect(
      page.getByText(/Eleven statements are judged on this page/),
    ).toBeVisible();
    await expect(page.getByText("holds up", { exact: true })).toBeVisible();
    const watched = page
      .locator("details")
      .filter({ hasText: "more being watched" });
    await expect(watched).not.toHaveAttribute("open", "");
    await watched.locator("summary").click();
    await expect(watched).toHaveAttribute("open", "");
    await expect(watched.getByText("watch", { exact: true })).toHaveCount(2);
  });

  test("method and sanity checks open on a click and nothing inside is coloured", async ({
    page,
  }) => {
    await page.goto("/proof");
    const fold = page
      .locator("details")
      .filter({ hasText: "Method and sanity checks" });
    await expect(fold).not.toHaveAttribute("open", "");
    await fold.locator("summary").click();
    await expect(fold).toHaveAttribute("open", "");
    await expect(
      fold.getByRole("heading", { name: /Against an estimated line/ }),
    ).toBeVisible();
    const estimated = fold.locator(
      'table[aria-label="Records at an estimated line"]',
    );
    await expect(estimated.locator("tbody tr")).toHaveCount(2);
    await expect(
      fold.getByRole("heading", {
        name: /Win rate by gap size, at an estimated line/,
      }),
    ).toBeVisible();
    // No --good / --bad anywhere below the estimated heading: colour is the
    // grade language and an estimated line is not a grade.
    const coloured = await fold.evaluate((d) =>
      [...d.querySelectorAll<HTMLElement>("td, span, p")]
        .map((el) => el.getAttribute("style") ?? "")
        .filter((s) => /--good|--bad/.test(s)),
    );
    expect(coloured).toEqual([]);
    await expect(
      fold.getByRole("heading", { name: /How the number is built/ }),
    ).toBeVisible();
    await expect(
      fold.getByRole("heading", { name: /How accurate our number is/ }),
    ).toBeVisible();
    await expect(fold).toContainText("Overall1934-0.12");
  });

  test("the glossary is where /glossary lands", async ({ page }) => {
    await page.goto("/proof#glossary");
    const glossary = page.locator("section#glossary");
    await expect(glossary).toBeVisible();
    await expect(
      glossary.getByRole("heading", { name: /Terms/ }),
    ).toBeVisible();
    expect(await glossary.locator("dt").count()).toBeGreaterThan(10);
  });

  test("links to every game we have rated", async ({ page }) => {
    await page.goto("/proof");
    await expect(
      page.getByRole("link", { name: "Every game we have rated →" }),
    ).toHaveAttribute("href", "/proof/records");
  });
});
