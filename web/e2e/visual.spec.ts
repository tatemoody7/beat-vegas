import { expect, test } from "@playwright/test";

// Screenshot comparisons, LOCAL-ONLY and opt-in (E2E_VISUAL=1 npm run
// e2e:visual). No baseline is committed -- e2e/__screenshots__ is gitignored --
// so the first run writes the baselines and every run after diffs against
// them; delete the folder to start over. Full-page captures of the four routes
// on the fixture week, which is the same every day by construction.

const ROUTES: [string, string][] = [
  ["board", "/"],
  ["results", "/results?week=all"],
  ["proof", "/proof"],
  ["game", "/game/900001"],
];

for (const [name, path] of ROUTES) {
  test(`${name} matches its local baseline`, async ({ page }) => {
    await page.goto(path, { waitUntil: "networkidle" });
    await expect(page).toHaveScreenshot(`${name}.png`, {
      fullPage: true,
      // Fonts and antialiasing differ a little run to run; layout does not.
      maxDiffPixelRatio: 0.01,
    });
  });
}
