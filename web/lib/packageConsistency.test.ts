import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// 2026-09-20: Dependabot's #167 bumped `react` to 19.3.0 and left `react-dom` at
// 19.2.4 — its npm group pairs react with its TYPES, not with the renderer.
// Merging it put a mismatch on main, and React refuses to start:
//   "Incompatible React versions: the react and react-dom packages must have
//    the exact same version."
// Every CI check passed. vitest runs in a node environment and never renders,
// `tsc` and `eslint` do not read versions, and CI does not run `npm run build` —
// the failure only appears when a page renders. So the guard has to be the
// versions themselves, which costs nothing and cannot be fooled.

const ROOT = join(import.meta.dirname, "..");
const pkg = JSON.parse(readFileSync(join(ROOT, "package.json"), "utf8"));
const lock = JSON.parse(readFileSync(join(ROOT, "package-lock.json"), "utf8"));

/** Pairs that must resolve to the EXACT same version, with what breaks if they do not. */
const MUST_MATCH: [string, string, string][] = [
  ["react", "react-dom", "React refuses to render with mismatched versions"],
  [
    "@types/react",
    "@types/react-dom",
    "the two type packages describe one API and drift produces phantom type errors",
  ],
];

const declared = (name: string): string | undefined =>
  pkg.dependencies?.[name] ?? pkg.devDependencies?.[name];

const installed = (name: string): string | undefined =>
  lock.packages?.[`node_modules/${name}`]?.version;

describe("packages that must move together", () => {
  it.each(MUST_MATCH)("%s and %s resolve to the same version", (a, b) => {
    const [va, vb] = [installed(a), installed(b)];
    expect(va, `${a} missing from the lockfile`).toBeTruthy();
    expect(vb, `${b} missing from the lockfile`).toBeTruthy();
    expect(
      vb,
      `${a} is ${va} but ${b} is ${vb} — React will refuse to render`,
    ).toBe(va);
  });

  it.each(MUST_MATCH)("%s and %s are declared the same way", (a, b) => {
    const [da, db] = [declared(a), declared(b)];
    if (da === undefined || db === undefined) return; // a types package may be absent
    // An exact pin on one and a caret on the other is how they drifted apart:
    // the caret floats, the pin does not.
    expect(da.startsWith("^"), `${a}="${da}" vs ${b}="${db}"`).toBe(
      db.startsWith("^"),
    );
  });
});

describe("the lockfile agrees with the manifest", () => {
  it("every exactly-pinned dependency is installed at that version", () => {
    const drift: string[] = [];
    for (const group of ["dependencies", "devDependencies"] as const) {
      for (const [name, range] of Object.entries(pkg[group] ?? {})) {
        if (typeof range !== "string" || !/^\d/.test(range)) continue; // exact pins only
        const got = installed(name);
        if (got && got !== range)
          drift.push(`${name}: pinned ${range}, locked ${got}`);
      }
    }
    expect(drift).toEqual([]);
  });
});
