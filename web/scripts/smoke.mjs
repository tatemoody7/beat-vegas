// Production smoke check, run by bv-ship after a deploy is READY (2026-10-13).
// Plain fetch, no browser, no Neon connection of its own: what a visitor would get.
//
//   node scripts/smoke.mjs --base https://beat-vegas.vercel.app
//
// Checks, each one PASS/FAIL on its own line; exits 1 if any failed:
//   - the pages answer 200 signed out (/, /results, /research, /records,
//     /login) and / is not bounced to /login
//   - the board links at least one game, and that game page answers 200
//   - every moved route in next.config.ts answers 308 to its destination
//   - /api/health answers 200 with ok:true (buildMissed / resultsStale print
//     as WARN: the board already shows them, a deploy did not cause them)
//   - /api/records?season=<this year> is a CSV with at least one data row
// The moved-route list is read from next.config.ts, so it never drifts.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const argv = process.argv.slice(2);
const at = argv.indexOf("--base");
const BASE = (at >= 0 ? argv[at + 1] : "https://beat-vegas.vercel.app").replace(
  /\/$/,
  "",
);
const HERE = path.dirname(fileURLToPath(import.meta.url));

let failed = 0;
const pass = (what) => console.log(`PASS  ${what}`);
const fail = (what) => {
  failed += 1;
  console.log(`FAIL  ${what}`);
};
const warn = (what) => console.log(`WARN  ${what}`);

async function get(p) {
  return fetch(BASE + p, {
    redirect: "manual",
    headers: { "user-agent": "bv-smoke" },
  });
}

export function movedRoutes(src) {
  const out = [];
  const re = /\{\s*source:\s*"([^"]+)",\s*destination:\s*"([^"]+)"\s*\}/g;
  for (const m of src.matchAll(re))
    out.push({ source: m[1], destination: m[2] });
  return out;
}

async function main() {
  for (const p of ["/", "/results", "/research", "/records", "/login"]) {
    const r = await get(p);
    if (r.status === 200) pass(`${p} 200`);
    else
      fail(
        `${p} ${r.status}${r.headers.get("location") ? " -> " + r.headers.get("location") : ""}`,
      );
  }

  const board = await (await get("/")).text();
  const game = board.match(/href="(\/game\/\d+)"/);
  if (!game) fail("/ links no game (empty board)");
  else {
    const r = await get(game[1]);
    if (r.status === 200) pass(`${game[1]} 200 (first game on the board)`);
    else fail(`${game[1]} ${r.status}`);
  }

  const moved = movedRoutes(
    fs.readFileSync(path.join(HERE, "..", "next.config.ts"), "utf8"),
  );
  if (moved.length === 0) fail("no moved routes parsed from next.config.ts");
  for (const { source, destination } of moved) {
    const r = await get(source);
    const loc = r.headers.get("location") ?? "";
    const got = new URL(loc || "/__none__", BASE);
    const want = new URL(destination, BASE);
    const ok =
      r.status === 308 &&
      got.pathname === want.pathname &&
      got.hash === want.hash;
    if (ok) pass(`${source} 308 -> ${destination}`);
    else
      fail(
        `${source} ${r.status} -> ${loc || "(no location)"}, wanted 308 -> ${destination}`,
      );
  }

  const h = await get("/api/health");
  let health = null;
  try {
    health = await h.json();
  } catch {
    /* reported below */
  }
  if (h.status === 200 && health?.ok === true) pass("/api/health ok:true");
  else fail(`/api/health ${h.status} ok=${health?.ok}`);
  if (health?.buildMissed)
    warn(`/api/health buildMissed (last built ${health.lastBuiltAt})`);
  if (health?.resultsStale) warn("/api/health resultsStale");

  const season = new Date().getUTCFullYear();
  const rec = await get(`/api/records?season=${season}`);
  const csv = rec.status === 200 ? await rec.text() : "";
  const rows = csv.split("\n").filter((l) => l.trim()).length - 1;
  if (rows > 0) pass(`/api/records?season=${season} ${rows} rows`);
  else
    fail(
      `/api/records?season=${season} ${rec.status}, ${Math.max(rows, 0)} rows`,
    );

  console.log(
    failed
      ? `\n${failed} check(s) failed against ${BASE}`
      : `\nall checks passed against ${BASE}`,
  );
  process.exit(failed ? 1 : 0);
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  main().catch((e) => {
    console.log(`FAIL  smoke crashed: ${e?.message ?? e}`);
    process.exit(1);
  });
}
