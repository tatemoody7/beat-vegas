import { expect, test as setup } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { AUTH_FILE, databaseUrl, E2E_PASSWORD } from "./helpers/env";

// Runs once before every browser project (playwright.config.ts `dependencies`).
//
// 1. Re-seed the fixture. The week is laid out relative to NOW, so a database
//    seeded yesterday has games that have since kicked off; re-seeding costs
//    about a second and makes the suite independent of when e2e:db last ran.
//    E2E_NO_SEED=1 skips it (a server whose database you are inspecting).
// 2. Log in ONCE and save the cookie. /api/login throttles at 10 attempts per
//    15 minutes per IP; the whole suite spends at most three.

setup("seed the fixture and sign in once", async ({ request }) => {
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
    expect(out).toContain('card {"bet":2,"edge":3,"pass":6');
  }

  const res = await request.post("/api/login", {
    data: { password: E2E_PASSWORD },
  });
  expect(res.status(), await res.text()).toBe(200);
  mkdirSync(dirname(AUTH_FILE), { recursive: true });
  await request.storageState({ path: AUTH_FILE });
});
