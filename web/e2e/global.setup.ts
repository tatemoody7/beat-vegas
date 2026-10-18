import { expect, test as setup } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { databaseUrl } from "./helpers/env";

// Runs once before every browser project (playwright.config.ts `dependencies`).
//
// Re-seed the fixture. The week is laid out relative to NOW, so a database
// seeded yesterday has games that have since kicked off; re-seeding costs
// about a second and makes the suite independent of when e2e:db last ran.
// E2E_NO_SEED=1 skips it (a server whose database you are inspecting).
// Nothing signs in any more (2026-10-18, D17): there is no login.

setup("seed the fixture", async () => {
  if (process.env.E2E_NO_SEED !== "1") {
    // A child `node`, not a dynamic import: the runner's module transform does
    // not serve .mjs named exports to another .mjs, and the seed is a plain
    // Node program anyway (the CI job runs it the same way).
    const out = execFileSync(
      process.execPath,
      [resolve(__dirname, "fixture/seed.mjs")],
      {
        env: { ...process.env, DATABASE_URL: databaseUrl() },
        encoding: "utf8",
      },
    );
    expect(out).toContain('card {"bet":2,"edge":4,"pass":6');
  }
});
