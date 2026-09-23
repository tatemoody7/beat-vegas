import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// e2e/FEATURE_PARITY.md is the list of what the site must keep doing, one
// line per assertion, each naming the Playwright test that proves it. This
// holds the list and the specs together in BOTH directions:
//
//   * every checklist line names a spec file that exists and a test title
//     that file declares (a renamed or deleted test cannot leave a stale line);
//   * every `test(...)` in e2e/*.spec.ts has a line (a new assertion cannot
//     land unlisted).
//
// Titles are compared as WRITTEN IN THE SOURCE, template placeholders
// included (`${id}: the three tiles ...`), because a parametrised test has one
// declaration and many runtime names.

const E2E = join(import.meta.dirname, "..", "e2e");
const CHECKLIST = join(E2E, "FEATURE_PARITY.md");

const LINE = /^- \[([a-z-]+)\] (.+?) — ([\w-]+\.spec\.ts) › "(.+)"$/;
// test("…") / test('…') / test(`…`), the title being the whole first argument.
const TEST_TITLE = /\btest\(\s*(["'`])((?:\\.|(?!\1)[^\\])*)\1/g;

type Line = { area: string; what: string; file: string; title: string };

function checklist(): Line[] {
  return readFileSync(CHECKLIST, "utf8")
    .split("\n")
    .filter((l) => l.startsWith("- "))
    .map((l) => {
      const m = l.match(LINE);
      if (!m) throw new Error(`FEATURE_PARITY.md line does not parse: ${l}`);
      return { area: m[1], what: m[2], file: m[3], title: m[4] };
    });
}

function specTitles(): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const f of readdirSync(E2E).filter((f) => f.endsWith(".spec.ts"))) {
    const src = readFileSync(join(E2E, f), "utf8");
    out.set(
      f,
      [...src.matchAll(TEST_TITLE)].map((m) => m[2]),
    );
  }
  return out;
}

describe("e2e/FEATURE_PARITY.md ↔ e2e/*.spec.ts", () => {
  const lines = checklist();
  const specs = specTitles();

  it("every checklist line names an existing spec and one of its tests", () => {
    const missing = lines
      .filter((l) => !(specs.get(l.file) ?? []).includes(l.title))
      .map((l) => `${l.file} › "${l.title}"`);
    expect(missing).toEqual([]);
  });

  it("every test in every spec has a checklist line", () => {
    const listed = new Set(lines.map((l) => `${l.file} › ${l.title}`));
    const unlisted: string[] = [];
    for (const [file, titles] of specs) {
      for (const t of titles) {
        if (!listed.has(`${file} › ${t}`)) unlisted.push(`${file} › "${t}"`);
      }
    }
    expect(unlisted).toEqual([]);
  });

  it("names each test once and every spec at least once", () => {
    const keys = lines.map((l) => `${l.file} › ${l.title}`);
    expect(new Set(keys).size).toBe(keys.length);
    const filesListed = new Set(lines.map((l) => l.file));
    expect([...specs.keys()].filter((f) => !filesListed.has(f))).toEqual([]);
    // Sanity: the specs are not empty and the regex found their tests.
    expect(lines.length).toBeGreaterThan(50);
    for (const [file, titles] of specs)
      expect(titles.length, file).toBeGreaterThan(0);
  });
});
