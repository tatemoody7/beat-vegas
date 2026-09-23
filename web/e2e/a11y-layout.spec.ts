import { expect, test } from "@playwright/test";
import { collectSilence, layoutMetrics } from "./helpers/metrics";

// Layout and silence, every page, both widths (the two browser projects):
// no horizontal scroll, one h1, the sticky header at its one height, no new
// tap target under 24px, and a console and network with nothing to report.
//
// Two things are pinned as KNOWN rather than asserted clean, because they are
// true of production today (measured 2026-09-23 on beat-vegas.vercel.app):
//
//  * SIGNED OUT at phone width -- what every public reader on a phone sees --
//    the Unlock link renders 14x68: `.bv-btn` sets no `display`, the <a> is
//    inline, and its block SVG collapses the width and stretches the height,
//    pushing the header to 87px instead of 69. Signed in, the Lock control is a
//    <button> (inline-block) and the header is 69 at both widths. test.fail()
//    marks the signed-out expectation: the day the link is fixed, the test
//    reports an unexpected pass and the annotation comes off.
//  * A handful of text links and buttons are under 24px tall: the answer bar's
//    matchup links (20px), PicksList's "details" / "edit" / "delete" (16px),
//    the game page's "Back to the board" (16px) and, on a phone, the wordmark
//    (20px). They are listed by name so a NEW small target anywhere else still
//    fails.

const PAGES: [string, string][] = [
  ["board", "/"],
  ["results", "/results?week=all"],
  ["proof", "/proof"],
  ["records", "/proof/records"],
  ["game", "/game/900001"],
  ["login", "/login"],
];

/** globals.css --header-h is 4.25rem (68px) plus the 1px bottom border. */
const HEADER_PX = 69;

/** The sub-24px targets production already has (see the file comment). */
const KNOWN_SMALL_TARGETS: RegExp[] = [
  /^a\S* "[^"]* @ [^"]*" \d+x20$/, // answer-bar matchup links
  /^button\S* "details" \d+x16$/, // PicksList row expander
  /^button\S* "(edit|delete)" \d+x16$/, // PicksList controls (signed in)
  /^a\S* "← Back to the board" \d+x16$/, // game page
  /^a\.shrink-0\S* "BEAT VEGAS/, // the wordmark at phone width
  /^a\.bv-btn\.bv-btn--ghost "Unlock" 14x68$/, // the collapsed Unlock control
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

    if (name !== "login") {
      // /login hides the nav and the Lock control (HeaderChrome), so its header
      // is the wordmark alone and shorter by design.
      test(`keeps the header at ${HEADER_PX}px`, async ({ page }) => {
        await page.goto(path, { waitUntil: "networkidle" });
        const m = await layoutMetrics(page);
        expect(m.headerHeight).toBe(HEADER_PX);
      });
    }
  });
}

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test(`keeps the header at ${HEADER_PX}px with the Unlock link showing`, async ({
    page,
    isMobile,
  }) => {
    test.fail(
      isMobile,
      "known: signed out at phone width the Unlock link renders 14x68 and the header measures 87px (production too, 2026-09-23)",
    );
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(page.getByRole("link", { name: "Unlock" })).toBeVisible();
    const m = await layoutMetrics(page);
    expect(m.headerHeight).toBe(HEADER_PX);
  });
});
