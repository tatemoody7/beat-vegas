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

test.describe("results", () => {
  // --- every bet we have placed (the ledger leads the page, 2026-09-28) ------

  const ledger = () => 'section[aria-label="Every bet"]';
  const signed = (n: number) => `${n >= 0 ? "+" : ""}${n.toFixed(2)}`;

  test("every bet: the summary strip, the week groups and the running units", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const strip = page.locator(ledger());
    // The real ledger opens first: 1-1 over three bets, -0.09u.
    const tabs = strip.getByRole("tablist", { name: "Which bets to show" });
    await expect(
      tabs.getByRole("tab", { name: `Our bets ${expected.ledger.realBets}` }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(strip).toContainText("Our bets50.0%");
    await expect(strip).toContainText(
      `${expected.ledger.real.record} · ${expected.ledger.realBets} bets · ${expected.ledger.real.units}u · ROI -4.5%`,
    );
    await expect(strip).toContainText(/could plausibly be \d+%–\d+%/);
    // The units curve sits under the strip: two graded weeks, dashed zero line.
    await expect(strip.locator(".recharts-wrapper")).toBeVisible();
    await expect(strip.locator(".recharts-reference-line line")).toHaveCount(1);
    // Stored clv -1.0 and +0.5 -> displayed +1.00 and -0.50, mean +0.25.
    await expect(strip).toContainText(
      `Line value${expected.ledger.avgPointsGained}points the market came toward us`,
    );
    await expect(strip).toContainText("50% of 2 lines moved our way");
    await expect(
      strip.getByRole("link", { name: "Download every bet (CSV)" }),
    ).toHaveAttribute("href", `/api/bets?season=${week.season}`);

    // One heading per week, newest first, each with its own record.
    const heads = strip.locator("h3.bv-day-head");
    await expect(heads).toHaveCount(2);
    await expect(heads.nth(0)).toHaveText(
      `Week ${week.week} · 1 bet · pending`,
    );
    await expect(heads.nth(1)).toHaveText(
      `Week ${week.prevWeek} · 2 bets · ${expected.ledger.real.record} · ${expected.ledger.real.units}u`,
    );

    // Running units accumulate oldest to newest; the pending row has none.
    const rows = strip.locator("tbody > tr.align-top");
    await expect(rows).toHaveCount(expected.ledger.realBets);
    await expect(rows.filter({ hasText: "Pending" })).toHaveCount(1);
    const graded = expected.picks
      .filter((p) => !p.isPaper && p.graded)
      .sort((a, b) => a.placedAt.getTime() - b.placedAt.getTime());
    let run = 0;
    for (const p of graded) {
      run = Math.round((run + (p.units as number)) * 100) / 100;
      const r = rows.filter({ hasText: p.game.home });
      await expect(r).toHaveCount(1);
      await expect(r).toContainText(`under ${p.line}`);
      await expect(r).toContainText(signed(p.units as number));
      await expect(r).toContainText(signed(run));
    }
    // The winner shows both first-half scores and the total it landed on.
    const won = rows.filter({ hasText: "Harrowgate" });
    const g13 = week.games.find((g) => g.id === 900013)!;
    await expect(won).toContainText(
      `${g13.played!.awayFh}–${g13.played!.homeFh} · ${g13.played!.awayFh + g13.played!.homeFh}`,
    );
  });

  test("every bet: won rows are tinted green and lost rows red, pending rows are not", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const strip = page.locator(ledger());
    const won = strip.locator("tbody > tr.bv-row--won");
    const lost = strip.locator("tbody > tr.bv-row--lost");
    await expect(won).toHaveCount(1);
    await expect(lost).toHaveCount(1);
    await expect(won).toContainText("Under");
    await expect(lost).toContainText("Over");
    const pending = strip.locator("tbody > tr.align-top").filter({
      hasText: "Pending",
    });
    await expect(pending).toHaveAttribute("class", "align-top");
    // The wash is the site's --good-bg / --bad-bg, not a new colour.
    const bg = (row: typeof won) =>
      row.evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(await bg(won)).toBe("rgba(61, 220, 132, 0.12)");
    expect(await bg(lost)).toBe("rgba(248, 113, 113, 0.12)");
    expect(await bg(pending)).toBe("rgba(0, 0, 0, 0)");
    // The paper ledger holds the push: grey, 0 units, out of the win rate.
    await strip
      .getByRole("tab", { name: `Paper ${expected.ledger.paperPicks}` })
      .click();
    const push = strip.locator("tbody > tr.bv-row--push");
    await expect(push).toHaveCount(1);
    await expect(push).toContainText("Push");
    await expect(push).toContainText("+0.00");
    await expect(strip).toContainText(
      `${expected.ledger.paper.record} · ${expected.ledger.paperPicks} bets`,
    );
  });

  test("every bet: the proof row shows the posted time, our number and the closing line", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const strip = page.locator(ledger());
    const won = strip
      .locator("tbody > tr.align-top")
      .filter({ hasText: "Harrowgate" });
    await won.getByRole("button", { name: "details" }).click();
    const detail = strip.locator("tr#bet-detail-1");
    const pick = expected.picks.find((p) => p.id === 1)!;
    await expect(detail).toContainText(
      `Our number then${pick.modelLine.toFixed(2)}`,
    );
    await expect(detail).toContainText("Why it was loggedBet · model gap · +");
    // Written 44 h before kickoff and logged 20 h before: the bet time leads,
    // the log time follows (bet_at, 2026-09-28).
    await expect(detail).toContainText(
      /Posted\w{3} \d+\/\d+ \d+:\d\d[ap]m ET · 44 h before kickoff · logged \w{3} \d+\/\d+ \d+:\d\d[ap]m ET/,
    );
    await expect(detail).toContainText(
      "Pricehardrockbet · price logged at the time",
    );
    await expect(detail).toContainText(
      `Closing line${pick.closingLine} at ${pick.closingPrice} · captured`,
    );
    await expect(detail).toContainText(`Note${pick.note}`);
    await won.getByRole("button", { name: "hide" }).click();
    await expect(detail).toHaveCount(0);
  });

  test("every bet: the CSV holds every pick with the stored clv beside its display", async ({
    request,
  }) => {
    const res = await request.get(`/api/bets?season=${week.season}`);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("text/csv");
    expect(res.headers()["content-disposition"]).toContain(
      `beatvegas-bets-${week.season}.csv`,
    );
    const lines = (await res.text()).trim().split("\n");
    expect(lines[0]).toBe(
      "season,week,placed_at_utc,bet_at_utc,kickoff_utc,ledger,away,home,market,bet,line,price,stake,bonus,book,price_provenance,verdict_at_pick,reason,gap_at_pick,model_line_at_pick,away_1h,home_1h,first_half_total,result,units,closing_line,closing_price,clv_points_stored,line_value_displayed,clv_prob,note",
    );
    expect(lines.length - 1).toBe(expected.picks.length);
    expect(lines.filter((l) => l.includes(",real,"))).toHaveLength(
      expected.ledger.realBets,
    );
    // The real winner: stored clv -1 is shown as +1.
    const won = lines.find(
      (l) => l.includes(",real,") && l.includes("Harrowgate"),
    )!;
    expect(won).toContain(",under,0.91,44.5,-112,-1,1,");
    expect((await request.get("/api/bets?season=abc")).status()).toBe(400);
  });

  test("the season comparison: every under, the paper rule, our bets, and signed in the model and the full game", async ({
    page,
  }) => {
    await page.goto("/results?week=all");
    const table = page.locator('table[aria-label="Season summary"]');
    await expect(table.locator("tbody tr")).toHaveCount(5);
    const rowText = async (label: string) =>
      (
        await table.locator("tr", { hasText: label }).first().innerText()
      ).replace(/\s+/g, " ");
    expect(await rowText("Every first-half under at the close")).toContain(
      `${marketFirstHalf.hit} ${marketFirstHalf.record} ${marketFirstHalf.units}`,
    );
    expect(
      await rowText("Every game that cleared the bar, on paper"),
    ).toContain(`${L.paper.hit} ${L.paper.record} ${L.paper.units}`);
    expect(await rowText("Our bets")).toContain(
      `50.0% ${L.real.record} ${L.real.units}`,
    );
    expect(await rowText("Our bets")).toContain(L.avgPointsGained); // line value column
    expect(await rowText("Model — first half")).toContain(
      `${model.hit} ${model.record} ${model.units}`,
    );
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
      tabs.getByRole("tab", { name: `Our bets ${L.realBets}` }),
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
    // (The same matchup also carries the paper PUSH row; keep to the ticket.)
    const lost = rows
      .filter({ hasText: "Thornbury" })
      .filter({ hasText: "Kestrel Point" })
      .filter({ hasNotText: "paper" });
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
    // Two tab lists carry "All N" now (the bet ledger and the picks table):
    // this test is about the picks table.
    await page
      .getByRole("tablist", { name: "Which picks to show" })
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

    test("a visitor gets the ledger and three comparison rows, not the Monday review", async ({
      page,
    }) => {
      await page.goto("/results?week=all");
      const strip = page.locator('section[aria-label="Every bet"]');
      await expect(strip).toContainText("Our bets50.0%");
      await strip
        .getByRole("tab", { name: `All ${expected.picks.length}` })
        .click();
      await expect(strip.locator("tbody > tr.align-top")).toHaveCount(
        expected.picks.length,
      );
      await expect(strip.getByRole("button", { name: "details" })).toHaveCount(
        expected.picks.length,
      );
      await expect(page.getByRole("button", { name: "edit" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "delete" })).toHaveCount(0);
      await expect(
        page.locator('table[aria-label="Season summary"] tbody tr'),
      ).toHaveCount(3);
      await expect(
        page.locator('section[aria-label="The Monday review, signed in"]'),
      ).toHaveCount(0);
      await expect(page.getByText("Your decisions")).toHaveCount(0);
    });
  });

  test("the default view is the latest week with a pick", async ({ page }) => {
    await page.goto("/results");
    await expect(page.locator(".bv-page-sub")).toHaveText(
      `week ${week.week} · ${week.season}`,
    );
    const thisWeekPicks = expected.picks.filter((p) => p.week === week.week);
    await page
      .getByRole("tablist", { name: "Which picks to show" })
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
