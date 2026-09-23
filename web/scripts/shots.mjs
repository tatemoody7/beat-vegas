// Full-page captures of every page and state, desktop (1440) and phone (390),
// plus the numbers the eye skims: height, horizontal overflow, scroll depth to
// the first answer, small text, small tap targets. Drives the INSTALLED Chrome
// through Playwright (no browser download) — the Browser pane cannot do this.
//
//   node scripts/shots.mjs --base http://localhost:3200 --label after
//
// Writes shots/<label>/<page>_<width>.png (+ _fold.png) and shots/<label>/report.json.
// Compare two labels with `node scripts/shots.mjs --diff before after` (the
// numbers) or `--pixdiff before after` (the pixels, via odiff; diff PNGs land in
// shots/<after>/diff_<page>_<width>.png only where something changed).
// The local dev server has no password gate (APP_PASSWORD unset), so no cookie.

import { chromium, devices } from "playwright";
import { compare } from "odiff-bin";
import fs from "node:fs";
import path from "node:path";

const args = Object.fromEntries(
  process.argv
    .slice(2)
    .join(" ")
    .split("--")
    .filter(Boolean)
    .map((s) => {
      const [k, ...v] = s.trim().split(/\s+/);
      return [k, v.join(" ") || true];
    }),
);
const BASE = args.base ?? "http://localhost:3000";
const LABEL = args.label ?? new Date().toISOString().slice(0, 10);
const OUT = path.resolve("shots", LABEL);

// Game ids drift week to week: --games 401858226,401856688 adds game pages,
// --extra "board_w2=/?week=2,results_w2=/results?week=2" adds anything else.
const GAMES = String(args.games ?? "")
  .split(",")
  .filter(Boolean);
const EXTRA = String(args.extra ?? "")
  .split(",")
  .filter(Boolean)
  .map((kv) => kv.split("="))
  .map(([k, ...v]) => [k, v.join("=")]);
const PAGES = [
  ["board", "/"],
  ["results", "/results?week=all"],
  ["proof", "/proof"],
  ["proof_records", "/proof/records"],
  ["login", "/login"],
  ...GAMES.map((id, i) => [`game_${i}_${id}`, `/game/${id}`]),
  ...EXTRA,
];

function metrics() {
  const doc = document.documentElement;
  const small = [...document.querySelectorAll("body *")]
    .filter((el) => el.children.length === 0 && el.textContent.trim())
    .map((el) => ({ el, px: parseFloat(getComputedStyle(el).fontSize) }))
    .filter((x) => x.px < 12).length;
  const targets = [
    ...document.querySelectorAll("a,button,select,input,[role=button]"),
  ]
    .map((el) => el.getBoundingClientRect())
    .filter((r) => r.width > 0 && r.height > 0);
  const under24 = targets.filter((r) => r.width < 24 || r.height < 24).length;
  const under44 = targets.filter((r) => r.width < 44 || r.height < 44).length;
  const firstAnswer =
    document.querySelector(".bv-card--lit") ??
    document.querySelector("[data-answer]") ??
    document.querySelector("h1");
  const header = document.querySelector("header");
  return {
    height: doc.scrollHeight,
    overflow: doc.scrollWidth - doc.clientWidth,
    headerHeight: header
      ? Math.round(header.getBoundingClientRect().height)
      : null,
    firstAnswerTop: firstAnswer
      ? Math.round(firstAnswer.getBoundingClientRect().top + window.scrollY)
      : null,
    textUnder12px: small,
    targetsUnder24: under24,
    targetsUnder44: under44,
    headings: [...document.querySelectorAll("h1,h2,h3")].map(
      (h) => `${h.tagName} ${h.textContent.trim().slice(0, 60)}`,
    ),
  };
}

async function shoot(ctx, tag, name, url, report) {
  const p = await ctx.newPage();
  await p.goto(BASE + url, { waitUntil: "networkidle", timeout: 90_000 });
  // Lazy team logos load on scroll; walk the page once before capturing.
  await p.evaluate(async () => {
    for (let y = 0; y < document.documentElement.scrollHeight; y += 700) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 60));
    }
    window.scrollTo(0, 0);
  });
  await p.waitForTimeout(600);
  const m = await p.evaluate(metrics);
  report.push({ page: name, viewport: tag, url, ...m });
  await p.screenshot({
    path: path.join(OUT, `${name}_${tag}.png`),
    fullPage: true,
  });
  await p.screenshot({ path: path.join(OUT, `${name}_${tag}_fold.png`) });
  await p.close();
}

async function capture() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  const desk = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  const phone = await browser.newContext({
    ...devices["iPhone 13"],
    deviceScaleFactor: 1,
    colorScheme: "dark",
    reducedMotion: "reduce",
  });
  const report = [];
  for (const [name, url] of PAGES) {
    await shoot(desk, "1440", name, url, report);
    await shoot(phone, "390", name, url, report);
    console.log("captured", name);
  }
  fs.writeFileSync(
    path.join(OUT, "report.json"),
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  printTable(report);
}

function printTable(report) {
  const pad = (s, n) => String(s).padEnd(n);
  console.log(
    pad("page", 24) +
      pad("vp", 6) +
      pad("height", 8) +
      pad("ovf", 5) +
      pad("hdr", 5) +
      pad("answer@", 9) +
      pad("<12px", 7) +
      pad("<24", 5) +
      "<44",
  );
  for (const r of report) {
    console.log(
      pad(r.page, 24) +
        pad(r.viewport, 6) +
        pad(r.height, 8) +
        pad(r.overflow, 5) +
        pad(r.headerHeight, 5) +
        pad(r.firstAnswerTop, 9) +
        pad(r.textUnder12px, 7) +
        pad(r.targetsUnder24, 5) +
        r.targetsUnder44,
    );
  }
}

function diff(a, b) {
  const ra = JSON.parse(
    fs.readFileSync(path.resolve("shots", a, "report.json")),
  );
  const rb = JSON.parse(
    fs.readFileSync(path.resolve("shots", b, "report.json")),
  );
  for (const x of ra) {
    const y = rb.find((r) => r.page === x.page && r.viewport === x.viewport);
    if (!y) continue;
    const d = (k) => `${x[k]} → ${y[k]}`;
    console.log(
      `${x.page} @${x.viewport}: height ${d("height")} · header ${d("headerHeight")} · ` +
        `<12px ${d("textUnder12px")} · <44 ${d("targetsUnder44")} · overflow ${d("overflow")}`,
    );
  }
}

// Pixel comparison of the full-page captures two labels share. The metric diff
// above says whether the page got taller; this says whether anything the eye
// would see moved. A diff PNG is written only when pixels differ, so an empty
// listing of diff_*.png after a run is itself the "nothing changed" evidence.
// It is a report, not a gate: it always exits 0.
async function pixdiff(a, b) {
  const dirA = path.resolve("shots", a);
  const dirB = path.resolve("shots", b);
  // Full-page files are <name>_<width>.png; the _fold.png crops are the same
  // pixels cut short, and diff_*.png are our own output from an earlier run.
  const files = fs
    .readdirSync(dirA)
    .filter((f) => /_\d+\.png$/.test(f) && !f.startsWith("diff_"))
    .filter((f) => fs.existsSync(path.join(dirB, f)))
    .sort();
  const rows = [];
  for (const f of files) {
    const m = f.match(/^(.*)_(\d+)\.png$/);
    const diffPath = path.join(dirB, `diff_${f}`);
    const r = await compare(
      path.join(dirA, f),
      path.join(dirB, f),
      diffPath,
      // antialiasing: font hinting differs run to run at glyph edges and is not
      // a change. threshold 0.1: odiff's per-pixel colour distance, loose enough
      // to swallow a gradient's rounding. failOnLayoutDiff: a page that grew is
      // reported as such rather than diffed against a shifted copy of itself.
      { antialiasing: true, threshold: 0.1, failOnLayoutDiff: true },
    );
    let verdict;
    if (r.match) {
      verdict = "same";
      // odiff does not write on a match, but never leave a stale diff behind.
      if (fs.existsSync(diffPath)) fs.rmSync(diffPath);
    } else if (r.reason === "layout-diff") {
      verdict = "layout";
    } else if (r.reason === "pixel-diff") {
      verdict = `pixels ${r.diffCount} (${r.diffPercentage.toFixed(1)}%)`;
    } else {
      verdict = `error ${r.reason}`;
    }
    rows.push({ page: m[1], viewport: m[2], verdict });
  }
  const pad = (s, n) => String(s).padEnd(n);
  console.log(pad("page", 24) + pad("vp", 6) + "verdict");
  for (const r of rows) {
    console.log(pad(r.page, 24) + pad(r.viewport, 6) + r.verdict);
  }
  if (rows.length === 0) {
    console.log(
      `(no <page>_<width>.png present in both shots/${a} and shots/${b})`,
    );
  }
}

if (args.diff) {
  const [a, b] = String(args.diff).split(/\s+/);
  diff(a, b);
} else if (args.pixdiff) {
  const [a, b] = String(args.pixdiff).split(/\s+/);
  await pixdiff(a, b);
} else {
  await capture();
}
