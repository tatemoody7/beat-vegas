import { expect, test } from "@playwright/test";
import { collectSilence, layoutMetrics } from "./helpers/metrics";

// Layout and silence, every page, both widths (the two browser projects):
// no horizontal scroll, one h1, the sticky header at its one height, no new
// tap target under 24px, and a console and network with nothing to report.
//
// Two things are pinned as KNOWN rather than asserted clean, because they are
// true of production today (measured 2026-09-23 on beat-vegas.vercel.app):
//
//  * (Retired 2026-09-28.) Signed out at phone width the header's Unlock link
//    used to render 14x68 and push the header to 87px; the login, the lock and
//    the cookie left the site altogether on 2026-10-18 (D17).
//  * A handful of text links are under 24px tall: the game page's "Back to the
//    board" (16px) and, on a phone, the wordmark (20px). They are listed by
//    name so a NEW small target anywhere else still fails. (The PicksList
//    "details" / "edit" / "delete" buttons left with the ledger, 2026-10-18.)

const PAGES: [string, string][] = [
  ["board", "/"],
  ["record", "/results"],
  ["research", "/research"],
  ["records", "/records"],
  ["game", "/game/900001"],
];

/** globals.css --header-h is 4.25rem (68px) plus the 1px bottom border. */
const HEADER_PX = 69;

/** The sub-24px targets production already has (see the file comment). */
const KNOWN_SMALL_TARGETS: RegExp[] = [
  /^a\S* "← Back to the board" \d+x16$/, // game page
  /^a\.shrink-0\S* "BEAT VEGAS/, // the wordmark at phone width
];

for (const [name, path] of PAGES) {
  test.describe(`${name} (${path})`, () => {
    test(`renders with no console errors and no failed requests`, async ({
      page,
    }) => {
      const silence = collectSilence(page);
      await page.goto(path, { waitUntil: "networkidle" });
      expect(silence.consoleErrors).toEqual([]);
      expect(silence.failedRequests).toEqual([]);
    });

    test(`has no horizontal scroll and exactly one h1`, async ({ page }) => {
      await page.goto(path, { waitUntil: "networkidle" });
      const m = await layoutMetrics(page);
      expect(m.overflow).toBe(0);
      expect(m.h1Count).toBe(1);
    });

    test(`adds no tap target under 24px beyond the known ones`, async ({
      page,
    }) => {
      await page.goto(path, { waitUntil: "networkidle" });
      const m = await layoutMetrics(page);
      const unexpected = m.targetsUnder24.filter(
        (d) => !KNOWN_SMALL_TARGETS.some((re) => re.test(d)),
      );
      expect(unexpected).toEqual([]);
    });

    test(`keeps the header at ${HEADER_PX}px`, async ({ page }) => {
      await page.goto(path, { waitUntil: "networkidle" });
      const m = await layoutMetrics(page);
      expect(m.headerHeight).toBe(HEADER_PX);
    });

    // No Lock or Unlock anywhere since 2026-10-18 (D17): the site has no login.
    test(`offers no Lock, Unlock or login link`, async ({ page }) => {
      await page.goto(path, { waitUntil: "networkidle" });
      await expect(page.getByRole("link", { name: "Unlock" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Lock" })).toHaveCount(0);
      await expect(page.locator('a[href="/login"]')).toHaveCount(0);
      await expect(page.getByText("Signed in")).toHaveCount(0);
    });
  });
}
