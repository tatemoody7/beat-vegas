import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";

// /proof/records (app/proof/records/page.tsx): one week at a time, opening on
// the latest week with a graded game; the gap to one decimal with its sign;
// the CSV link that hands over the whole season.

const { week, thisWeek } = fixture();
const fmt1 = (n: number) => n.toFixed(1);

test.describe("every game we have rated", () => {
  test("opens on the latest graded week and shows only its rows", async ({
    page,
  }) => {
    await page.goto("/proof/records");
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
      `/proof/records?season=${week.season}&week=${week.week}`,
    );
    await expect(
      page.getByText(`${thisWeek.length} of ${week.games.length} games`),
    ).toBeVisible();
    const rows = page.locator("table.bv-table tbody tr");
    await expect(rows).toHaveCount(thisWeek.length);
    await expect(rows.locator("td").first()).toHaveText(String(week.week));
  });

  test("shows each game's line, our number and the gap to one decimal, signed", async ({
    page,
  }) => {
    await page.goto(`/proof/records?season=${week.season}&week=${week.week}`);
    const rows = page.locator("table.bv-table tbody tr");
    const cells = await rows.evaluateAll((trs) =>
      trs.map((tr) =>
        [...tr.querySelectorAll("td")].map(
          (td) => td.textContent?.trim() ?? "",
        ),
      ),
    );
    for (const c of cells) {
      // Week, Matchup, Full game, Line, Our number, Gap, Actual first half, Result.
      expect(c).toHaveLength(8);
      expect(c[5]).toMatch(/^([+-]\d+\.\d|0\.0)$/);
    }
    for (const g of thisWeek) {
      const row = rows
        .filter({ hasText: `${g.away}` })
        .filter({ hasText: g.home });
      const lineUsed = g.hr ? g.hr[0].line : null;
      const gap =
        lineUsed === null ? null : Math.round((lineUsed - g.bv) * 100) / 100;
      const tds = row.locator("td");
      await expect(tds.nth(2)).toHaveText(fmt1(g.fg.total));
      await expect(tds.nth(4)).toHaveText(fmt1(g.bv));
      if (gap !== null) {
        await expect(tds.nth(3)).toHaveText(fmt1(lineUsed!));
        await expect(tds.nth(5)).toHaveText(
          `${gap > 0 ? "+" : ""}${fmt1(gap)}`,
        );
      }
      if (g.played) {
        const fh = g.played.homeFh + g.played.awayFh;
        await expect(tds.nth(6)).toHaveText(String(fh));
        await expect(tds.nth(7)).toHaveText(fh < lineUsed! ? "Under" : "Over");
      } else {
        await expect(tds.nth(6)).toHaveText("—");
        await expect(tds.nth(7)).toHaveText("Pending");
      }
    }
  });

  test("the previous week is one click away and holds its two graded games", async ({
    page,
  }) => {
    await page.goto("/proof/records");
    await page
      .getByRole("link", { name: String(week.prevWeek), exact: true })
      .click();
    await page.waitForURL(
      `**/proof/records?season=${week.season}&week=${week.prevWeek}`,
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
    await page.goto("/proof/records");
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
    await page.goto("/proof/records");
    for (const term of [
      "Full game",
      "Line",
      "Our number",
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
