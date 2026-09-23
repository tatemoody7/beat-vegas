import { expect, test, type Page } from "@playwright/test";
import { restoreSetting, setSetting } from "./helpers/db";
import { etParts, fixture } from "./helpers/fixture";

// The board (app/page.tsx) against the fixture week, feature by feature. Every
// number asserted here is derived in e2e/fixture/expected.mjs from the same rows
// the seed wrote, by a port of the site's own rules that lib/e2eFixture.test.ts
// holds to the TypeScript originals -- so this file checks the RENDER, not the
// arithmetic twice.

const { week, expected, thisWeek, byId } = fixture();

/** The game rows on the page, in DOM order: id, href, badge text, section label. */
async function rows(page: Page) {
  return page.$$eval("a.bv-card[id^='game-']", (els) =>
    els.map((el) => ({
      id: Number(el.id.replace("game-", "")),
      href: el.getAttribute("href"),
      badge: el.querySelector("span[aria-label]")?.textContent?.trim() ?? "",
      section: el.closest("section")?.getAttribute("aria-label") ?? "(none)",
      lit: el.classList.contains("bv-card--lit"),
      chips: [...el.querySelectorAll(".bv-badge")].map((c) =>
        c.textContent?.trim(),
      ),
    })),
  );
}

test.describe("the board", () => {
  test("every row links to its game page and the ids are the fixture's week", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.locator("h1.bv-page-title")).toHaveText(
      `Board · Week ${week.week}`,
    );
    const r = await rows(page);
    expect(r.map((x) => x.id).sort()).toEqual(thisWeek.map((g) => g.id).sort());
    for (const x of r) expect(x.href).toBe(`/game/${x.id}`);
  });

  test("groups the week Thu, Fri, Sat, then Played last", async ({ page }) => {
    await page.goto("/");
    const labels = await page.$$eval(
      "section[aria-label] > h2.bv-day-head",
      (hs) =>
        hs.map((h) => [
          h.closest("section")?.getAttribute("aria-label"),
          h.textContent?.trim(),
        ]),
    );
    expect(labels.map((l) => l[0])).toEqual(["Thu", "Fri", "Sat", "Played"]);
    expect(labels[3][1]).toBe(`Played · ${expected.playedIds.length}`);
    const r = await rows(page);
    for (const x of r) {
      const g = byId.get(x.id)!;
      const day = etParts(g.kick).weekday;
      expect(x.section, `${x.id}`).toBe(
        expected.playedIds.includes(x.id) ? "Played" : day,
      );
    }
    // Played is the last section on the page.
    expect(r[r.length - 1].section).toBe("Played");
  });

  test("numbers the week best to worst in the expected order", async ({
    page,
  }) => {
    await page.goto("/");
    const r = await rows(page);
    const rank = new Map(expected.rankOrder.map((id, i) => [id, i + 1]));
    for (const x of r) {
      if (expected.playedIds.includes(x.id)) {
        expect(x.badge, `${x.id}`).toBe("won"); // 27 under 30.5, settled
      } else {
        expect(x.badge, `${x.id}`).toBe(`#${rank.get(x.id)}`);
      }
    }
    // Within each day the rows run in rank order.
    const bySection = new Map<string, number[]>();
    for (const x of r) {
      if (x.section === "Played") continue;
      const list = bySection.get(x.section) ?? [];
      list.push(rank.get(x.id)!);
      bySection.set(x.section, list);
    }
    for (const [section, ranks] of bySection) {
      expect(ranks, section).toEqual([...ranks].sort((a, b) => a - b));
    }
  });

  test("lights exactly the two BET rows", async ({ page }) => {
    await page.goto("/");
    const lit = page.locator("a.bv-card--lit");
    await expect(lit).toHaveCount(expected.betIds.length);
    const ids = await lit.evaluateAll((els) =>
      els.map((el) => Number(el.id.replace("game-", ""))).sort(),
    );
    expect(ids).toEqual([...expected.betIds].sort());
  });

  test("states the tier counts", async ({ page }) => {
    await page.goto("/");
    const c = expected.counts;
    await expect(
      page.getByText(`${c.bet} bet · ${c.edge} watch · ${c.pass} pass`, {
        exact: true,
      }),
    ).toBeVisible();
  });

  test("states this week’s bar exactly", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText(expected.barLine, { exact: true }),
    ).toBeVisible();
  });

  test("the answer bar names the live bet, the placed one, the closest three and the next build", async ({
    page,
  }) => {
    await page.goto("/");
    const bar = page.locator('div[aria-label="This week at a glance"]');
    await expect(bar).toBeVisible();
    await expect(bar).toContainText(expected.answer.headline);
    await expect(bar).toContainText(expected.answer.slotsLine);
    const items = bar.locator("ul").first().locator("li");
    await expect(items).toHaveCount(expected.answer.bets.length);
    for (const [i, b] of expected.answer.bets.entries()) {
      const li = items.nth(i);
      await expect(li.getByRole("link")).toHaveText(b.matchup);
      await expect(li.getByRole("link")).toHaveAttribute(
        "href",
        `/game/${b.gameId}`,
      );
      await expect(li).toContainText(b.numbers);
      await expect(li.locator(".bv-badge")).toHaveCount(b.picked ? 1 : 0);
      if (b.picked)
        await expect(li.locator(".bv-badge")).toHaveText("bet logged");
    }
    await expect(
      bar.getByRole("heading", { name: "Closest to a bet" }),
    ).toBeVisible();
    const near = bar.locator("ul").nth(1).locator("li");
    await expect(near).toHaveCount(expected.answer.closest.length);
    for (const [i, c] of expected.answer.closest.entries()) {
      await expect(near.nth(i).getByRole("link")).toHaveText(c.matchup);
      await expect(near.nth(i)).toContainText(c.numbers);
      await expect(near.nth(i)).toContainText(c.needs);
    }
    await expect(bar).toContainText(
      /Next build (Tue|Thu|Fri|Sat) \d{1,2}:\d{2}(am|pm)?–\d{1,2}:\d{2}(am|pm) ET/,
    );
  });

  test("marks the game with a logged ticket", async ({ page }) => {
    await page.goto("/");
    const r = await rows(page);
    for (const x of r) {
      const chips = x.chips.filter((c) => c === "bet logged");
      expect(chips.length, `${x.id}`).toBe(
        expected.pickedIds.has(x.id) ? 1 : 0,
      );
    }
  });

  test("the Hard Rock filter sets ?hr=1, presses the chip and hides the games without a line", async ({
    page,
  }) => {
    await page.goto("/");
    const hr = page.getByRole("button", { name: "Hard Rock line posted" });
    await expect(hr).toHaveAttribute("aria-pressed", "false");
    await hr.click();
    await page.waitForURL(/\?hr=1$/);
    await expect(hr).toHaveAttribute("aria-pressed", "true");
    const withLine = thisWeek.filter((g) => g.hr !== null).map((g) => g.id);
    const r = await rows(page);
    expect(r.map((x) => x.id).sort()).toEqual(withLine.sort());
    await expect(
      page.getByText(`· ${thisWeek.length} games before filters`),
    ).toBeVisible();
  });

  test("My teams shows only the followed program, one filter at a time", async ({
    page,
  }) => {
    await page.goto("/?hr=1");
    const mine = page.getByRole("button", { name: "My teams" });
    await mine.click();
    await page.waitForURL(/\?mine=1$/);
    await expect(mine).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByRole("button", { name: "Hard Rock line posted" }),
    ).toHaveAttribute("aria-pressed", "false");
    const r = await rows(page);
    const followed = thisWeek
      .filter((g) => g.away === "Kansas State" || g.home === "Kansas State")
      .map((g) => g.id);
    expect(followed.length).toBeGreaterThan(0);
    expect(r.map((x) => x.id).sort()).toEqual(followed.sort());
    // Clicking the active chip clears it.
    await mine.click();
    await page.waitForURL((u) => u.search === "");
    await expect(mine).toHaveAttribute("aria-pressed", "false");
  });

  test("?days=sat keeps only Saturday’s games", async ({ page }) => {
    await page.goto("/?days=sat");
    const saturday = thisWeek
      .filter((g) => etParts(g.kick).weekday === "Sat")
      .map((g) => g.id);
    const r = await rows(page);
    expect(r.map((x) => x.id).sort()).toEqual(saturday.sort());
    const labels = await page.$$eval("section[aria-label]", (ss) =>
      ss.map((s) => s.getAttribute("aria-label")),
    );
    expect(labels.filter((l) => l !== "Played")).toEqual(["Sat"]);
  });

  test("every banner is silent in the clean state", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("div[role=status]")).toHaveCount(0);
    for (const text of [
      "did not run.",
      "Results are",
      "Real money is paused.",
      "Real money is off until the pause switch can be read.",
      "No model number this week.",
      "Hard Rock has not posted first-half lines yet.",
      "Nothing clears the bar this week.",
    ]) {
      await expect(page.getByText(text)).toHaveCount(0);
    }
  });
});

// The two banners the clean fixture never shows, by putting the gauges into the
// state that raises them and putting them back. Serial, and the only place the
// suite writes to the database after the seed.
test.describe.serial("banners driven by app_settings", () => {
  test("a low Odds API budget lights the ops banner and /api/health warns", async ({
    page,
    request,
  }) => {
    const before = await setSetting("odds_credits_remaining", "100");
    try {
      await page.goto("/");
      const banner = page.locator("div[role=status]");
      await expect(banner).toHaveCount(1);
      await expect(banner).toContainText("One thing needs attention.");
      await expect(banner).toContainText(
        "Odds API credits low: 100 left this cycle.",
      );
      const health = await (await request.get("/api/health")).json();
      expect(health.warnings).toHaveLength(1);
      expect(health.warnings[0]).toContain("Odds API credits low: 100");
    } finally {
      await restoreSetting("odds_credits_remaining", before);
    }
    await page.goto("/");
    await expect(page.locator("div[role=status]")).toHaveCount(0);
  });

  test("the real-money pause shows its banner and /api/health reports it", async ({
    page,
    request,
  }) => {
    const before = await setSetting("rule_paused", "true");
    try {
      await page.goto("/");
      await expect(page.getByText("Real money is paused.")).toBeVisible();
      await expect(
        page.getByText(
          "Every real-money first-half pick is refused until the rule has been reviewed. Paper picks still log and count toward the record.",
        ),
      ).toBeVisible();
      const health = await (await request.get("/api/health")).json();
      expect(health.rulePaused).toBe(true);
      expect(health.rulePauseReadable).toBe(true);
    } finally {
      await restoreSetting("rule_paused", before);
    }
    await page.goto("/");
    await expect(page.getByText("Real money is paused.")).toHaveCount(0);
  });
});
