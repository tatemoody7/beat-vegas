import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";

// /records (app/records/page.tsx; /records until 2026-09-28): one week at a time, opening on
// the latest week with a graded game; the gap to one decimal with its sign;
// the CSV link that hands over the whole season.

const { week, thisWeek, expected } = fixture();
const fmt1 = (n: number) => n.toFixed(1);

// Hard Rock Records (fact-check audit 2026-10-17): each game graded on Hard
// Rock's line and price as the last scheduled card before kickoff froze them.
// The fresh card carries the upcoming games; the seed's earlier card carries
// each played game's last quote captured two hours before the week's first
// played kickoff.
const cardItems = expected.card.items as unknown as {
  game_id: number;
  hr_line: number | null;
  hr_price: number | null;
}[];
function hrAtCard(g: (typeof thisWeek)[number]) {
  if (g.played) {
    const played = week.games.filter((x) => x.played && x.week === g.week);
    const built = Math.min(...played.map((x) => x.kick.getTime())) - 7_200_000;
    const q = (g.hr ?? []).filter((h) => h.capturedAt.getTime() <= built).pop();
    return q ? { line: q.line, price: q.under } : null;
  }
  const it = cardItems.find((i) => i.game_id === g.id);
  return it && it.hr_line !== null && it.hr_price !== null
    ? { line: it.hr_line, price: it.hr_price }
    : null;
}
const american = (p: number) => (p > 0 ? `+${p}` : `${p}`);

test.describe("every game we have rated", () => {
  test("opens on the latest graded week and shows only its rows", async ({
    page,
  }) => {
    await page.goto("/records");
    await expect(page.locator("h1.bv-page-title")).toHaveText(
      "Every game we have rated",
    );
    // The week pills: the current one carries the accent ring.
    const active = page.locator("a.bv-pill.ring-1", {
      hasText: String(week.week),
    });
    await expect(active).toHaveCount(1);
    await expect(active).toHaveAttribute(
      "href",
      `/records?season=${week.season}&week=${week.week}&view=hr`,
    );
    // Hard Rock Records opens first when the season has Hard Rock lines.
    await expect(
      page.getByRole("tab", { name: "Hard Rock Records" }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      page.getByText(`${thisWeek.length} of ${week.games.length} games`),
    ).toBeVisible();
    const rows = page.locator("table.bv-table tbody tr");
    await expect(rows).toHaveCount(thisWeek.length);
    await expect(rows.locator("td").first()).toHaveText(String(week.week));
  });

  test("lists no season before 2023 (training history stays off the site)", async ({
    page,
  }) => {
    await page.goto("/records");
    const pills = page.locator("a.bv-pill .bv-pill-value");
    await expect(pills.filter({ hasText: String(week.season) })).toHaveCount(1);
    await expect(pills.filter({ hasText: "2005" })).toHaveCount(0);
  });

  test("grades each game on Hard Rock's line and price at the last scheduled card", async ({
    page,
  }) => {
    await page.goto(`/records?season=${week.season}&week=${week.week}`);
    const rows = page.locator("table.bv-table tbody tr");
    const cells = await rows.evaluateAll((trs) =>
      trs.map((tr) =>
        [...tr.querySelectorAll("td")].map(
          (td) => td.textContent?.trim() ?? "",
        ),
      ),
    );
    for (const c of cells) {
      // Week, Matchup, Full game, Our number, Hard Rock, Price, Gap, Actual, Result.
      expect(c).toHaveLength(9);
    }
    for (const g of thisWeek) {
      const row = rows
        .filter({ hasText: `${g.away}` })
        .filter({ hasText: g.home });
      const tds = row.locator("td");
      await expect(tds.nth(2)).toHaveText(fmt1(g.fg.total));
      await expect(tds.nth(3)).toHaveText(fmt1(g.bv));
      const q = hrAtCard(g);
      if (q !== null) {
        const gap = Math.round((q.line - g.bv) * 100) / 100;
        await expect(tds.nth(4)).toHaveText(fmt1(q.line));
        await expect(tds.nth(5)).toHaveText(american(q.price));
        await expect(tds.nth(6)).toHaveText(`${gap > 0 ? "+" : ""}${fmt1(gap)}`);
      } else {
        await expect(tds.nth(4)).toHaveText("—");
      }
      if (g.played) {
        const fh = g.played.homeFh + g.played.awayFh;
        await expect(tds.nth(7)).toHaveText(String(fh));
        await expect(tds.nth(8)).toHaveText(
          q === null
            ? "No verified Hard Rock line"
            : fh < q.line
              ? "Under"
              : "Over",
        );
      } else {
        await expect(tds.nth(7)).toHaveText("—");
        await expect(tds.nth(8)).toHaveText("Pending");
      }
    }
    await expect(page.getByTestId("records-totals")).toContainText(
      "at Hard Rock's line on the last scheduled card",
    );
  });

  test("Market Research grades on the consensus close, as a record with no units", async ({
    page,
  }) => {
    await page.goto(
      `/records?season=${week.season}&week=${week.prevWeek}&view=market`,
    );
    await expect(
      page.getByRole("tab", { name: "Market Research" }),
    ).toHaveAttribute("aria-selected", "true");
    const totals = page.getByTestId("records-totals");
    await expect(totals).toContainText("a research benchmark, not a bet");
    await expect(totals).not.toContainText("units");
    await expect(page.locator("table.bv-table thead th")).toHaveText([
      "Week",
      "Matchup",
      "Full game",
      "Our number",
      "Close",
      "Gap",
      "Actual first half",
      "Result",
    ]);
    await expect(page.locator("dl dt", { hasText: "Close" })).toBeVisible();
  });

  test("the previous week is one click away and holds its two graded games", async ({
    page,
  }) => {
    await page.goto("/records");
    await page
      .getByRole("link", { name: String(week.prevWeek), exact: true })
      .click();
    await page.waitForURL(
      `**/records?season=${week.season}&week=${week.prevWeek}&view=hr`,
    );
    const rows = page.locator("table.bv-table tbody tr");
    const prev = week.games.filter((g) => g.week === week.prevWeek);
    await expect(rows).toHaveCount(prev.length);
    await expect(rows.filter({ hasText: "Under" })).toHaveCount(1);
    await expect(rows.filter({ hasText: "Over" })).toHaveCount(1);
  });

  test("offers the whole season as a CSV download", async ({
    page,
    request,
  }) => {
    await page.goto("/records");
    const link = page.getByRole("link", {
      name: `Download all of ${week.season}`,
    });
    await expect(link).toHaveAttribute(
      "href",
      `/api/records?season=${week.season}`,
    );
    await expect(link).toHaveAttribute("download", "");
    const res = await request.get(`/api/records?season=${week.season}`);
    expect(res.status()).toBe(200);
    expect((await res.text()).trim().split("\n")).toHaveLength(
      week.games.length + 1,
    );
  });

  test("the legend explains the columns without a tooltip", async ({
    page,
  }) => {
    await page.goto("/records");
    for (const term of [
      "Full game",
      "Our number",
      "Hard Rock",
      "Gap",
      "Scored after",
    ]) {
      await expect(
        page.locator("dl dt", { hasText: term }).first(),
      ).toBeVisible();
    }
    await expect(page.locator("table th[title]")).toHaveCount(0);
  });
});
