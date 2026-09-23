import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";

// /results (app/results/page.tsx): the scoreboard, the season summary table,
// the breakdown toggle, the decisions strip and the picks ledger, against the
// six picks and nine results the fixture seeds. Every record here is worked
// out from the fixture rows, not typed in.

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
const model = record(
  played.map((g) => {
    const fh = g.played!.homeFh + g.played!.awayFh;
    const lineUsed = g.hr![0].line; // predictions.line_used = the first HR capture
    return { under: fh < lineUsed, units: unitFor(fh < lineUsed) };
  }),
);

const usd = (n: number) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: Number.isInteger(n) ? 0 : 2,
  });

test.describe("results", () => {
  test("the scoreboard: the rule on paper, my money, line value", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    await expect(page.locator("h1.bv-page-title")).toHaveText("Results");
    const band = page.locator('section[aria-label="Scoreboard"]');
    await expect(band).toContainText(`The rule, on paper${L.paper.hit}`);
    await expect(band).toContainText(
      `${L.paper.record} · ${L.paper.n} picks · ${L.paper.units}u`,
    );
    await expect(band).toContainText(/plausibly \d+%–\d+%/);
    await expect(band).toContainText(`My money${usd(L.bankrollUsd)}`);
    await expect(band).toContainText(
      `${L.real.record} · ${L.realBets} bets · ${L.real.units}u · ROI `,
    );
    await expect(band).toContainText("0 against the verdict");
    await expect(band).toContainText(
      `modelled from the ledger (${usd(L.startUsd)} + units × ${usd(L.unitUsd)}), not reconciled with the Hard Rock account`,
    );
    // Paper line value: the one graded paper pick closed 1.0 toward us.
    await expect(band).toContainText(
      "Line value+1.00points the market came toward us",
    );
    await expect(band).toContainText(
      `${L.pctFavourable.replace(".0%", "%")} of ${L.real.n} lines moved our way`,
    );
  });

  test("the season summary compares market, model, the rule, you and the full game", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const table = page.locator('table[aria-label="Season summary"]');
    const rowText = async (label: string) =>
      (
        await table.locator("tr", { hasText: label }).first().innerText()
      ).replace(/\s+/g, " ");
    expect(await rowText("Market — first half")).toContain(
      `${marketFirstHalf.hit} ${marketFirstHalf.record} ${marketFirstHalf.units}`,
    );
    expect(await rowText("Model — first half")).toContain(
      `${model.hit} ${model.record} ${model.units}`,
    );
    expect(await rowText("The rule — paper")).toContain(
      `${L.paper.hit} ${L.paper.record} ${L.paper.units}`,
    );
    expect(await rowText("You — real money")).toContain(
      `50.0% ${L.real.record} ${L.real.units}`,
    );
    expect(await rowText("You — real money")).toContain(L.avgPointsGained); // line value column
    expect(await rowText("Market — full game")).toContain(
      `${marketFullGame.hit} ${marketFullGame.record} ${marketFullGame.units}`,
    );
  });

  test("the breakdown's three views each account for every pick", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const section = page.locator('section[aria-label="Breakdown"]');
    const realTotal = expected.picks.filter((p) => !p.isPaper).length;
    const paperTotal = expected.picks.filter((p) => p.isPaper).length;

    // By week: two weeks, Real money (Bets) + Paper (Picks) columns.
    await expect(section.getByRole("tab", { name: "By week" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    let body = section.locator("tbody tr");
    await expect(body).toHaveCount(2);
    const weekRows = await body.evaluateAll((trs) =>
      trs.map((tr) =>
        [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim()),
      ),
    );
    // Columns: week, bets, W-L-P, units, roi, clv, picks, W-L-P, units, roi, clv.
    expect(weekRows.map((r) => r[0])).toEqual([
      String(week.prevWeek),
      String(week.week),
    ]);
    expect(weekRows.reduce((a, r) => a + Number(r[1]), 0)).toBe(realTotal);
    expect(weekRows.reduce((a, r) => a + Number(r[6]), 0)).toBe(paperTotal);

    // By reason: every pick was a model-gap pick.
    await section.getByRole("tab", { name: "By reason" }).click();
    body = section.locator("tbody tr");
    await expect(body).toHaveCount(1);
    await expect(body.first()).toContainText(
      "Model gap — Hard Rock 1.75+ above our number",
    );
    const reasonRow = await body.first().locator("td").allInnerTexts();
    expect(Number(reasonRow[1])).toBe(realTotal);
    expect(Number(reasonRow[6])).toBe(paperTotal);

    // By blocker: paper only, one row per gate that blocked a real bet.
    await section.getByRole("tab", { name: "By blocker" }).click();
    body = section.locator("tbody tr");
    const blockers = expected.picks
      .filter((p) => p.isPaper)
      .map((p) => p.blocker);
    await expect(body).toHaveCount(new Set(blockers).size);
    const blockerRows = await body.evaluateAll((trs) =>
      trs.map((tr) =>
        [...tr.querySelectorAll("td")].map((td) => td.textContent?.trim()),
      ),
    );
    expect(blockerRows.reduce((a, r) => a + Number(r[1]), 0)).toBe(paperTotal);
    expect(blockerRows.map((r) => r[0])).toEqual(
      expect.arrayContaining([
        "Hard Rock's price was too short",
        "Hard Rock's line was below the market",
        "Past the 5-bet week",
      ]),
    );
  });

  test("the decisions strip reads the graded real tickets with the favourable sign", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const strip = page
      .locator("dl")
      .filter({ hasText: "Lines that moved our way" })
      .first();
    // Each DecisionsStrip row is <div><dt/><dd/></div>: the dd beside the dt.
    const row = async (label: string) =>
      (
        await strip
          .locator("dt", { hasText: new RegExp(`^${label}$`) })
          .locator("xpath=following-sibling::dd")
          .innerText()
      ).trim();
    // Stored clv is closing − bet (−1.0 and +0.5); the page shows −mean = +0.25.
    expect(await row("Line value")).toBe(`${L.avgPointsGained} (${L.real.n})`);
    expect(await row("Lines that moved our way")).toBe(
      `${L.pctFavourable} (${L.real.n})`,
    );
    expect(await row("At or better than the open")).toBe(`50.0% (${L.real.n})`);
    expect(await row("Better than the close")).toBe(`50.0% (${L.real.n})`);
    expect(await row("Real bets against the verdict")).toBe(
      `0 of ${L.realBets}`,
    );
  });

  test("the picks ledger: every pick, the labels, and line value negated", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const tabs = page.getByRole("tablist", { name: "Which picks to show" });
    await expect(
      tabs.getByRole("tab", { name: `My bets ${L.realBets}` }),
    ).toHaveAttribute("aria-selected", "true");
    await tabs
      .getByRole("tab", { name: `All ${expected.picks.length}` })
      .click();
    const rows = page
      .locator("table")
      .filter({ hasText: "Your line" })
      .locator("tbody > tr.align-top");
    await expect(rows).toHaveCount(expected.picks.length);

    // The graded real WIN: -110, Under, +0.91u, and the stored clv of -1.0 shown as +1.00.
    const won = rows
      .filter({ hasText: "Harrowgate" })
      .filter({ hasNotText: "paper" });
    await expect(won).toHaveCount(1);
    await expect(won).toContainText("under 45.5");
    await expect(won).toContainText("-110");
    await expect(won).toContainText("Under");
    await expect(won).toContainText("+0.91");
    await expect(won).toContainText(L.clvDisplayed[0]);
    // The graded real LOSS: -115, Over, -1.00u, and the stored clv of +0.5 shown as -0.50.
    const lost = rows
      .filter({ hasText: "Thornbury" })
      .filter({ hasText: "Kestrel Point" });
    await expect(lost).toContainText("-115");
    await expect(lost).toContainText("Over");
    await expect(lost).toContainText("-1.00");
    await expect(lost).toContainText(L.clvDisplayed[1]);
    // The pending real ticket and the two pending paper picks.
    await expect(rows.filter({ hasText: "Pending" })).toHaveCount(3);
    await expect(rows.filter({ hasText: "paper" })).toHaveCount(L.paperPicks);

    // The frozen decision under "details": verdict / reason labels and the blocker.
    // 900003, Eastbrook @ Fairhaven (Eastbrook also hosts last week's paper cap pick).
    const priced = rows
      .filter({ hasText: "Fairhaven" })
      .filter({ hasText: "paper" });
    await priced.getByRole("button", { name: "details" }).click();
    const detail = page.locator("tr[id^='pick-detail-']");
    await expect(detail).toContainText(
      "Watch · model gap · +3.5 vs our number · blocked by price too short",
    );
    await expect(detail).toContainText(`Our number then44`);
  });

  test("signed in, pending picks can be edited or deleted; graded ones cannot", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    await page
      .getByRole("tab", { name: `All ${expected.picks.length}` })
      .click();
    const rows = page
      .locator("table")
      .filter({ hasText: "Your line" })
      .locator("tbody > tr.align-top");
    const pending = rows.filter({ hasText: "Pending" });
    const graded = rows.filter({ hasNotText: "Pending" });
    await expect(pending.getByRole("button", { name: "edit" })).toHaveCount(3);
    await expect(pending.getByRole("button", { name: "delete" })).toHaveCount(
      3,
    );
    await expect(graded.getByRole("button", { name: "edit" })).toHaveCount(0);
    await expect(graded.getByRole("button", { name: "delete" })).toHaveCount(0);
  });

  test.describe("signed out", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test("the ledger is readable but nothing can be edited or deleted", async ({
      page,
    }) => {
      await page.goto("/results?week=all");
      await page
        .getByRole("tab", { name: `All ${expected.picks.length}` })
        .click();
      const rows = page
        .locator("table")
        .filter({ hasText: "Your line" })
        .locator("tbody > tr.align-top");
      await expect(rows).toHaveCount(expected.picks.length);
      await expect(page.getByRole("button", { name: "edit" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "delete" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "details" })).toHaveCount(
        expected.picks.length,
      );
    });
  });

  test("the default view is the latest week with a pick", async ({ page }) => {
    await page.goto("/results");
    await expect(page.locator(".bv-page-sub")).toHaveText(
      `week ${week.week} · ${week.season}`,
    );
    const thisWeekPicks = expected.picks.filter((p) => p.week === week.week);
    await page
      .getByRole("tab", { name: `All ${thisWeekPicks.length}` })
      .click();
    const rows = page
      .locator("table")
      .filter({ hasText: "Your line" })
      .locator("tbody > tr.align-top");
    await expect(rows).toHaveCount(thisWeekPicks.length);
    // Filtered to one week, the Week column is dropped.
    await expect(
      page
        .locator("table")
        .filter({ hasText: "Your line" })
        .locator("th", { hasText: "Week" }),
    ).toHaveCount(0);
  });
});
