import { expect, test } from "@playwright/test";
import { fixture } from "./helpers/fixture";
import { FACTOR_NOTE } from "../lib/score";

// /game/[id] (app/components/GameDetail.tsx): the decision block must show the
// SAME numbers the board row carried (it rebuilds the whole week to get the
// rank), the kill numbers where the sentence names them, and the per-book line
// movement. Since 2026-10-18 (final-2026 plan, D2) there is no log control, no
// "bet logged" or cap chip, and every rating reads in paper wording.

const { expected, rowById } = fixture();

const fmt = (n: number | null, dp = 1) => (n === null ? "—" : n.toFixed(dp));
const american = (p: number) => (p > 0 ? `+${p}` : `${p}`);

const BET_LOGGED = 900001; // BET #1 (a frozen real ticket sits on it in the database)
const BET_OPEN = 900002; // BET #2
const PRICE_BLOCKED = 900003; // EDGE, blocker price
const GAP_SHORT = 900005; // EDGE, blocker gap
const HR_ALT = 900015; // EDGE, blocker hr_alt_line: the feed's newest HR quote is an alternate
const PLAYED = 900012;

test.describe("the game page", () => {
  for (const id of [BET_LOGGED, BET_OPEN, PRICE_BLOCKED, GAP_SHORT, PLAYED]) {
    test(`${id}: the three tiles, the rank and the sentence match the board row`, async ({
      page,
    }) => {
      const r = rowById.get(id)!;
      await page.goto(`/game/${id}`);
      await expect(page.locator("h1")).toHaveText(
        new RegExp(`${r.game.away}\\s*@\\s*${r.game.home}`),
      );
      const tiles = page.locator("section.bv-card").first();
      const hr = r.check?.hrLine ?? null;
      const hrText =
        hr === null
          ? "no line yet"
          : `u${fmt(hr)}${r.check?.hrUnderPrice == null ? "" : ` ${american(r.check.hrUnderPrice)}`}`;
      await expect(tiles).toContainText(`Hard Rock${hrText}`);
      await expect(tiles).toContainText(
        `Market${r.cons.cur === null ? "—" : `u${fmt(r.cons.cur)}`}`,
      );
      await expect(tiles).toContainText(`Our number${fmt(r.game.bv)}`);
      if (r.kickedOff) {
        // A played game states its result in place of the action.
        await expect(tiles).toContainText(
          `Won · first half ${r.game.played!.homeFh + r.game.played!.awayFh}, line ${fmt(hr)}`,
        );
        // No rank once the game has kicked off: the badge reads the result.
        expect(r.boardRank).toBeNull();
        await expect(
          page.locator("span.font-mono", { hasText: /^#\d+$/ }),
        ).toHaveCount(0);
      } else {
        await expect(tiles.locator("p.text-base")).toHaveText(r.edge.action);
        await expect(
          page.getByText(`#${r.boardRank}`, { exact: true }),
        ).toBeVisible();
      }
    });
  }

  test("names the kill number for a game short of the bar and the kill price for a dear one", async ({
    page,
  }) => {
    const short = rowById.get(GAP_SHORT)!;
    await page.goto(`/game/${GAP_SHORT}`);
    await expect(page.locator("section.bv-card").first()).toContainText(
      `It becomes a signal at ${fmt(short.edge.killLine)} or higher.`,
    );
    const dear = rowById.get(PRICE_BLOCKED)!;
    await page.goto(`/game/${PRICE_BLOCKED}`);
    await expect(page.locator("section.bv-card").first()).toContainText(
      `needs ${american(dear.edge.killPrice!)} or better.`,
    );
  });

  test("a Hard Rock alternate line: the tile shows the last main line with its time, paper only", async ({
    page,
  }) => {
    const r = rowById.get(HR_ALT)!;
    expect(r.edge.blocker).toBe("hr_alt_line");
    expect(r.check!.hrLive).toBe(false);
    // lib/labels.ts::hrQuoteText: the held-over quote carries its ET capture time.
    const t = new Date(r.check!.hrAsOf!);
    const p = Object.fromEntries(
      new Intl.DateTimeFormat("en-US", {
        timeZone: "America/New_York",
        weekday: "short",
        hour: "numeric",
        minute: "2-digit",
        hourCycle: "h23",
      })
        .formatToParts(t)
        .map((x) => [x.type, x.value]),
    );
    const h = Number(p.hour) % 24;
    const when = `${p.weekday} ${h % 12 === 0 ? 12 : h % 12}:${p.minute}${h >= 12 ? "pm" : "am"}`;
    await page.goto(`/game/${HR_ALT}`);
    const tiles = page.locator("section.bv-card").first();
    await expect(tiles).toContainText(
      `Hard Rocku${fmt(r.check!.hrLine)} ${american(r.check!.hrUnderPrice!)} · as of ${when}`,
    );
    await expect(tiles.locator("p.text-base")).toHaveText(r.edge.action);
    await expect(page.getByRole("button", { name: /Log/ })).toHaveCount(0);
  });

  // The read-only record (2026-10-18, D2/D17): the decision block carries the
  // Hard Rock note and nothing to click; the ticketed game and the open one
  // read the same way, with no chip, no price age and no QB warning.
  test("the decision block carries the Hard Rock note and offers no log control, chip or warning", async ({
    page,
  }) => {
    for (const id of [BET_OPEN, BET_LOGGED]) {
      await page.goto(`/game/${id}`);
      const card = page.locator("section.bv-card").first();
      await expect(card).toContainText(
        "Priced at Hard Rock Bet (Florida). Your book’s first-half total may differ; the line and price to beat are the ones shown.",
      );
      await expect(page.getByRole("button", { name: /Log/ })).toHaveCount(0);
      await expect(page.getByText("Unlock to log a pick")).toHaveCount(0);
      await expect(page.getByText("Already logged")).toHaveCount(0);
      await expect(card.locator(".bv-badge")).toHaveCount(0);
      await expect(page.getByTestId("price-age")).toHaveCount(0);
      await expect(page.getByTestId("qb-unknown")).toHaveCount(0);
      await expect(
        page.getByText(/cap slot \d|bet cap|bet logged/),
      ).toHaveCount(0);
    }
  });

  // Every rating reads in paper wording before kickoff; a played game shows
  // its result.
  test("the rating reads in paper wording before kickoff, and the result after it", async ({
    page,
  }) => {
    await page.goto(`/game/${BET_OPEN}`);
    const card = page.locator("section.bv-card").first();
    await expect(card).toContainText("Paper signal:");
    await expect(card).not.toContainText("Bet one unit");
    await expect(card).not.toContainText("at kickoff");
    await expect(
      page.getByText("The factor read publishes at kickoff."),
    ).toHaveCount(0);
    // A played game is history: its result is public.
    await page.goto(`/game/${PLAYED}`);
    await expect(page.locator("section.bv-card").first()).toContainText(
      "Won · first half 27, line 30.5",
    );
  });

  // Q5 (Tate 2026-10-15): the factors explain the line in scoring words; the
  // seed stores the OLD wording, so this also proves stored rows are rewritten.
  test("words every factor by scoring, never the bet, under the screen's note", async ({
    page,
  }) => {
    let directed = 0;
    for (const id of [BET_LOGGED, BET_OPEN, PRICE_BLOCKED, GAP_SHORT, HR_ALT]) {
      await page.goto(`/game/${id}`);
      const why = page.locator("section.bv-card", {
        hasText: "What is behind it",
      });
      await expect(
        why.locator('p[aria-label="What the factors can tell you"]'),
      ).toHaveText(FACTOR_NOTE);
      const texts = await why.locator(".bv-fac-text").allTextContents();
      expect(texts.length, `${id}`).toBeGreaterThan(0);
      for (const t of texts) expect(t, `${id}`).not.toMatch(/the under/);
      directed += texts.filter((t) => t.includes("points to")).length;
    }
    // The seed words some factors "— helps the under." / "works against the
    // under": they must arrive rewritten.
    expect(directed).toBeGreaterThan(0);
  });

  // Tate 2026-10-16: the wind is one row in the factors list, the steady wind
  // from the newest card forecast, green at 10+ mph; no gusts, no weather box.
  test("shows the newest card forecast's steady wind as a coloured factor row", async ({
    page,
  }) => {
    await page.goto(`/game/${BET_LOGGED}`);
    const row = page.locator(".bv-fac-row", { hasText: "Wind 11 mph" });
    await expect(row).toHaveText("Wind 11 mph — points to less scoring.");
    expect(
      await row.evaluate((el) => (el as HTMLElement).style.background),
    ).toMatch(/rgba\(22, ?163, ?74/);
    await expect(page.getByText(/gust/i)).toHaveCount(0);
    await expect(page.locator('div[aria-label="Weather"]')).toHaveCount(0);
    // The fixture's undated Sunday row ("... mph wind at kickoff") is not shown.
    await expect(
      page.locator(".bv-fac-text", { hasText: "wind at kickoff" }),
    ).toHaveCount(0);
    // No analysis box on any game page (removed 2026-10-16).
    await expect(page.locator('section[aria-label="Analysis"]')).toHaveCount(0);
  });

  test("lists every book's open and current line, Hard Rock's move included", async ({
    page,
  }) => {
    const r = rowById.get(BET_LOGGED)!;
    await page.goto(`/game/${BET_LOGGED}`);
    const lines = page.locator("section.bv-card", { hasText: "Lines" }).first();
    await expect(lines).toContainText(
      `Market line${fmt(r.cons.open)} → ${fmt(r.cons.cur)}`,
    );
    const bookRows = lines.locator("table tbody tr");
    await expect(bookRows).toHaveCount(r.check!.books.length);
    expect(r.check!.books.length).toBeGreaterThanOrEqual(2);
    const hrRow = bookRows.filter({ hasText: "Hard Rock" });
    const [open, cur] = [
      r.game.hr![0].line,
      r.game.hr![r.game.hr!.length - 1].line,
    ];
    await expect(hrRow.locator("td").nth(1)).toHaveText(fmt(open));
    await expect(hrRow.locator("td").nth(2)).toHaveText(fmt(cur));
    await expect(hrRow.locator("td").nth(3)).toHaveText(
      cur === open
        ? "no move"
        : `${cur > open ? "+" : ""}${(cur - open).toFixed(1)}`,
    );
  });

  test("says when no book has posted a first half yet", async ({ page }) => {
    await page.goto("/game/900011");
    await expect(
      page.getByText(
        "No sportsbook has posted a first-half total for this game yet.",
      ),
    ).toBeVisible();
    // The sentence now names the basis too ("our reference line is 0.4
    // above"), so the Lines row is matched exactly.
    await expect(
      page.getByText("Our reference line", { exact: true }),
    ).toBeVisible();
  });

  test("a non-numeric id and an unknown id are 404s", async ({
    page,
    request,
  }) => {
    for (const path of ["/game/abc", "/game/123456", "/game/-1"]) {
      const res = await request.get(path);
      expect(res.status(), path).toBe(404);
    }
    await page.goto("/game/123456");
    await expect(page.locator("h1")).toHaveText("Nothing here.");
    await expect(
      page.getByRole("link", { name: "Back to the board" }),
    ).toBeVisible();
  });

  test("the played game links back to its row on the board", async ({
    page,
  }) => {
    await page.goto(`/game/${PLAYED}`);
    await expect(
      page.getByRole("link", { name: "← Back to the board" }),
    ).toHaveAttribute("href", `/#game-${PLAYED}`);
    expect(expected.playedIds).toContain(PLAYED);
  });
});
