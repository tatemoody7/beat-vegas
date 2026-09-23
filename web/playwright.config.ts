import { defineConfig, devices } from "@playwright/test";
import { AUTH_FILE, databaseUrl, E2E_PASSWORD } from "./e2e/helpers/env";

// The e2e lane: the real Next.js app, rendered by a real browser, against a
// real Postgres holding the SYNTHETIC fixture week (e2e/fixture/). Nothing here
// ever reaches Neon: DATABASE_URL defaults to the pgserver sandbox
// scripts/e2e-db.sh boots, seed.mjs refuses a neon.tech URL outright, and the
// server this config starts gets its environment from HERE, not from web/.env.
//
//   npm run e2e:db      # sandbox on 54329, schema, seed
//   npm run e2e         # every project, headless, the installed Chrome
//   npm run e2e:ui      # Playwright's UI
//   E2E_VISUAL=1 npm run e2e:visual   # toHaveScreenshot, local-only baselines
//
// Locally the server is `next dev` (no build step, ~1 s to first byte after
// the first compile) on port 3400 -- 3000 is main's dev server and 3100-3199
// are the worktree dev servers (scripts/dev-worktree.sh). In CI, and under
// E2E_PROD=1, it is `next start` on the production build, which is what
// actually ships. E2E_BASE_URL points the suite at a server you started
// yourself (a worktree on 31xx) and skips the webServer entirely.
//
// The password gate is ON (APP_PASSWORD set) so the signed-out / signed-in
// split is exercised: the `setup` project logs in ONCE and every browser
// project reuses that storageState. /api/login throttles at 10 attempts per
// 15 minutes per IP, so the specs are written to spend at most three.

const CI = !!process.env.CI;
const PORT = 3400;
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;
const PROD = CI || !!process.env.E2E_PROD;

const serverEnv: Record<string, string> = {
  ...(process.env as Record<string, string>),
  DATABASE_URL: databaseUrl(),
  APP_PASSWORD: E2E_PASSWORD,
  // Never the Neon HTTP lane: the sandbox is plain Postgres over TCP.
  NEON_HTTP: "",
  NEXT_TELEMETRY_DISABLED: "1",
  // The bankroll numbers the ledger specs assert are the defaults.
  BANKROLL_USD: "100",
  UNIT_USD: "10",
};

// The downloaded Chromium in CI (installed by the workflow); the machine's own
// Chrome locally, like scripts/shots.mjs, so nothing has to be downloaded.
const channel = CI ? undefined : "chrome";

export default defineConfig({
  testDir: "./e2e",
  // One server, one database, and a serial block that mutates app_settings:
  // parallel workers would race on the same rows.
  fullyParallel: false,
  workers: 1,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  outputDir: "test-results",
  snapshotPathTemplate: "e2e/__screenshots__/{platform}/{arg}{ext}",
  use: {
    baseURL: BASE_URL,
    colorScheme: "dark",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    // `next dev` compiles a route on its first request; give it room.
    navigationTimeout: PROD ? 30_000 : 90_000,
    actionTimeout: 15_000,
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: PROD ? `npx next start -p ${PORT}` : `npx next dev -p ${PORT}`,
        url: `${BASE_URL}/login`,
        reuseExistingServer: !CI,
        timeout: 180_000,
        env: serverEnv,
        stdout: "ignore",
        stderr: "pipe",
      },
  projects: [
    {
      name: "setup",
      testMatch: /global\.setup\.ts/,
      use: { channel },
    },
    {
      name: "desktop-chrome",
      dependencies: ["setup"],
      testIgnore: /visual\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        browserName: "chromium",
        channel,
        viewport: { width: 1440, height: 900 },
        deviceScaleFactor: 1,
        storageState: AUTH_FILE,
      },
    },
    {
      name: "iphone-13",
      dependencies: ["setup"],
      testIgnore: /visual\.spec\.ts/,
      use: {
        ...devices["iPhone 13"],
        // The device descriptor asks for WebKit; the lane is Chromium-only.
        browserName: "chromium",
        channel,
        deviceScaleFactor: 1,
        storageState: AUTH_FILE,
      },
    },
    // Screenshot comparisons, opt-in and local-only: no baseline is committed
    // (e2e/__screenshots__ is gitignored), so the first run writes one and the
    // next run diffs against it. E2E_VISUAL=1 npm run e2e:visual.
    ...(process.env.E2E_VISUAL === "1"
      ? [
          {
            name: "visual",
            dependencies: ["setup"],
            testMatch: /visual\.spec\.ts/,
            use: {
              ...devices["Desktop Chrome"],
              browserName: "chromium" as const,
              channel,
              viewport: { width: 1440, height: 900 },
              deviceScaleFactor: 1,
              storageState: AUTH_FILE,
            },
          },
        ]
      : []),
  ],
});
