import { expect, test, type Page } from "@playwright/test";
import { restoreSetting, setSetting } from "./helpers/db";
import { etParts, fixture } from "./helpers/fixture";
import { RESEARCH_BANNER } from "../lib/labels";
import { PASS_HEAD } from "../lib/boardKey";
import { SLIM_LEAD } from "../app/components/ResearchStrip";

// The board (app/page.tsx) against the fixture week, feature by feature. Every
// number asserted here is derived in e2e/fixture/expected.mjs from the same rows
// the seed wrote, by a port of the site's own rules that lib/e2eFixture.test.ts
// holds to the TypeScript originals -- so this file checks the RENDER, not the
// arithmetic twice.

const { week, expected, thisWeek, byId, rowById } = fixture();

/** The game rows on the page, in DOM order: id, href, badge text, section label. */
async function rows(page: Page) {
  return page.$$eval("a.bv-card[id^='game-']", (els) =>
    els.map((el) => ({
      id: Number(el.id.replace("game-", "")),
      href: el.getAttribute("href"),
      badge: el.querySelector("span[aria-label]")?.textContent?.trim() ?? "",
      badgeColor:
        (el.querySelector("span[aria-label]") as HTMLElement | null)?.style
          .background ?? "",
      text: el.querySelector("p")?.textContent?.trim() ?? "",
      section: el.closest("section")?.getAttribute("aria-label") ?? "(none)",
      lit: el.classList.contains("bv-card--lit"),
      chips: [...el.querySelectorAll(".bv-badge")].map((c) =>
        c.textContent?.trim(),
      ),
    })),
  );
}

test.describe("the board", () => {
  test("opens with the slim line and nothing else above the games", async ({
    page,
  }) => {
    await page.goto("/");
    const slim = page.locator('p[aria-label="Research status"]');
    await expect(slim).toContainText(
      `${SLIM_LEAD} · six paper strategies judged against the closing price · up to 12 of 30 readings · next read`,
    );
    await expect(slim.getByRole("link")).toHaveAttribute("href", "/research");
    await expect(slim.locator(".bv-pill")).toHaveCount(0);
    await expect(page.locator('p[aria-label="What this is"]')).toHaveCount(0);
    // No bar line, no key line, no separate list (Tate 2026-10-16).
    await expect(
      page.locator('p[aria-label="How to read the Board"]'),
    ).toHaveCount(0);
    await expect(page.getByText(/^Bar this week/)).toHaveCount(0);
    await expect(
      page.locator('section[aria-label="Research top 10"]'),
    ).toHaveCount(0);
    // The slim line sits above the week heading, never inside the board.
    const slimBox = await slim.boundingBox();
    const heading = await page.locator("h1.bv-page-title").boundingBox();
    expect(slimBox!.y).toBeLessThan(heading!.y);
  });

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

  test("lists the week as one ranked list, then Played last", async ({
    page,
  }) => {
    await page.goto("/");
    const labels = await page.$$eval("section[aria-label]", (ss) =>
      ss.map((x) => x.getAttribute("aria-label")),
    );
    expect(labels).toEqual(["Ranked", "Played"]);
    await expect(
      page.locator('section[aria-label="Played"] > h2.bv-day-head'),
    ).toHaveText(`Played · ${expected.playedIds.length}`);
    const r = await rows(page);
    for (const x of r) {
      expect(x.section, `${x.id}`).toBe(
        expected.playedIds.includes(x.id) ? "Played" : "Ranked",
      );
    }
    expect(r[r.length - 1].section).toBe("Played");
  });

  test("says a Pass in a few words under one heading; a Pass is red at every rank", async ({
    page,
  }) => {
    await page.goto("/");
    const r = (await rows(page)).filter((x) => x.section === "Ranked");
    const passes = r.filter((x) => x.text.startsWith("Pass"));
    for (const x of passes) {
      expect(x.text, `${x.id}`).toMatch(
        /^Pass · (leans over \d+\.\d|short of the bar \(needs \d+\.\d\)|on our number|no model number yet)$/,
      );
      // A Pass is red at every rank (audit 2026-10-17: green only for a paper signal).
      expect(x.badgeColor, `${x.id}`).toBe("var(--bad)");
    }
    const head = page.locator('p[aria-label="Pass games"]');
    if (passes.length === 0) {
      await expect(head).toHaveCount(0);
    } else {
      await expect(head).toHaveText(PASS_HEAD);
      // The heading comes right before the first Pass row, and every row after
      // it is a Pass: Pass rows score under the amber band, so they sort last.
      const firstPassId = passes[0].id;
      const next = await page.$eval(
        'p[aria-label="Pass games"]',
        (el) => el.nextElementSibling?.id ?? "",
      );
      expect(next).toBe(`game-${firstPassId}`);
      const at = r.findIndex((x) => x.id === firstPassId);
      expect(r.slice(at).every((x) => x.text.startsWith("Pass"))).toBe(true);
    }
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
    // One list: the rows run #1, #2, #3 ... down the page (Q2, 2026-10-15).
    const ranks = r
      .filter((x) => x.section === "Ranked")
      .map((x) => rank.get(x.id)!);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(ranks[0]).toBe(1);
  });

  test("green marks only a paper signal, and the Board says a gap is not an edge", async ({
    page,
  }) => {
    await page.goto("/");
    const r = (await rows(page)).filter((x) => x.section === "Ranked");
    for (const x of r) {
      expect(x.badgeColor === "var(--good)", `${x.id}`).toBe(
        expected.betIds.includes(x.id),
      );
    }
    await expect(page.getByTestId("board-honesty")).toContainText(
      "Green marks a paper signal, not a proven bet",
    );
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

  // The log path left the site (2026-10-18, D2): no tier-count line, no
  // "bet logged" chip, no price age and no QB warning on any row.
  test("carries no tier-count line, no chip, no price age and no QB warning on any row", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByText(/ watch · \d+ pass/)).toHaveCount(0);
    await expect(page.getByTestId("price-age")).toHaveCount(0);
    await expect(page.getByTestId("qb-unknown")).toHaveCount(0);
    const r = await rows(page);
    expect(r.length).toBeGreaterThan(0);
    for (const x of r) expect(x.chips, `${x.id}`).toEqual([]);
  });

  // Final-2026 plan D4 build 5: a price says when it was captured; a row with
  // no Hard Rock quote shows no time (one is never invented).
  test("every row with a Hard Rock price shows its as-of time beside it, and no other row does", async ({
    page,
  }) => {
    await page.goto("/");
    const r = await rows(page);
    let withTime = 0;
    for (const x of r) {
      const check = rowById.get(x.id)?.check ?? null;
      const stamp = page.locator(`#game-${x.id} [data-testid="hr-as-of"]`);
      if (check !== null && check.hrLine !== null && check.hrAsOf !== null) {
        withTime += 1;
        await expect(stamp, `${x.id}`).toHaveText(
          /^as of (Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d{1,2}:\d{2} (AM|PM) ET$/,
        );
      } else {
        await expect(stamp, `${x.id}`).toHaveCount(0);
      }
    }
    expect(withTime).toBeGreaterThan(0);
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
    expect(labels.filter((l) => l !== "Played")).toEqual(["Ranked"]);
  });

  test("every banner is silent in the clean state", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("div[role=status]")).toHaveCount(0);
    for (const text of [
      "did not run.",
      "Results are",
      "Our bets are paused.",
      "Real money is off until the pause switch can be read.",
      "No model number this week.",
      "Hard Rock has not posted first-half lines yet.",
      "Nothing clears the bar this week.",
    ]) {
      await expect(page.getByText(text)).toHaveCount(0);
    }
  });
});

test.describe("the board, read by anyone", () => {
  test("the Hard Rock filter is the only chip", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Hard Rock line posted" }),
    ).toBeVisible();
    await expect(page.locator("button.bv-chip")).toHaveCount(1);
    await expect(page.getByRole("button", { name: "My teams" })).toHaveCount(0);
  });

  // The read-only record (2026-10-18, D2/D15/D17): everyone reads the same
  // board -- the ranks, the lit BET rows, the order -- in paper wording, never
  // bet wording, with the one sentence in the footer.
  test("the footer carries the one sentence and every rating reads in paper wording", async ({
    page,
  }) => {
    await page.goto("/");
    // The one sentence lives in the footer (Q10, 2026-10-15; reworded D15).
    await expect(
      page.locator('footer p[aria-label="Research season"]'),
    ).toHaveText(RESEARCH_BANNER);

    await expect(
      page.locator('div[aria-label="This week at a glance"]'),
    ).toHaveCount(0);
    await expect(page.getByText(/ watch · \d+ pass/)).toHaveCount(0);
    const r = await rows(page);
    const rank = new Map(expected.rankOrder.map((id, i) => [id, i + 1]));
    const upcoming = r.filter((x) => x.section !== "Played");
    expect(upcoming.length).toBeGreaterThan(0);
    for (const x of upcoming) {
      expect(x.badge, `${x.id}`).toBe(`#${rank.get(x.id)}`);
      expect(x.lit, `${x.id}`).toBe(expected.betIds.includes(x.id));
      expect(x.chips, `${x.id}`).not.toContain("bet logged");
    }
    await expect(page.getByText(/Bet one unit/)).toHaveCount(0);
    await expect(page.getByText("Rating publishes at kickoff.")).toHaveCount(0);
    // The slim research line is public too (2026-10-14, slimmed 2026-10-15).
    await expect(page.locator('p[aria-label="Research status"]')).toContainText(
      "six paper strategies judged against the closing price",
    );
    // The weekly cap was the real-money rule: no slot, no over-cap chip, no
    // "real money needs" clause anywhere (2026-10-18). The fixture's ticketed
    // BET reads like any other row.
    await expect(
      page.getByText(/cap slot \d|bet cap|real money needs/),
    ).toHaveCount(0);
    const ticketed = expected.picks.find(
      (p) => p.game.kick.getTime() > Date.now(),
    );
    if (ticketed) {
      await page.goto(`/game/${ticketed.game.id}`);
      await expect(
        page.getByText(/cap slot \d|bet cap|real money needs|bet logged/),
      ).toHaveCount(0);
    }
  });
});

// The two banners the clean fixture never shows, by putting the gauges into the
// state that raises them and putting them back. Serial, and the only place the
// suite writes to the database after the seed.
test.describe.serial("banners driven by app_settings", () => {
  test("a low Odds API budget lights the ops banner for everyone and /api/health warns", async ({
    page,
    request,
  }) => {
    const before = await setSetting("odds_credits_remaining", "100");
    try {
      await page.goto("/");
      // The ops warning renders for everyone since 2026-10-18 (D17): a
      // research record shows its own state.
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

  test("the real-money switch is nothing the site reads: the board and /api/health ignore it", async ({
    page,
    request,
  }) => {
    const before = await setSetting("rule_paused", "true");
    try {
      await page.goto("/");
      // Real money ended 2026-10-18 (D2): the switch stays on in the database
      // and nothing on the site reads it; the footer sentence says what this is.
      await expect(
        page.locator('footer p[aria-label="Research season"]'),
      ).toHaveText(RESEARCH_BANNER);
      await expect(page.getByText("Our bets are paused.")).toHaveCount(0);
      await expect(
        page.getByText("Real money is off until the pause switch can be read."),
      ).toHaveCount(0);
      const health = await (await request.get("/api/health")).json();
      expect(health).not.toHaveProperty("rulePaused");
      expect(health).not.toHaveProperty("rulePauseReadable");
    } finally {
      await restoreSetting("rule_paused", before);
    }
  });
});
