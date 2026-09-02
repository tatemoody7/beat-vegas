import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// web/data/*.json mirror the repo's data/*.json (the web build cannot import
// above its root, and Vercel's root is web/). Guard against drift: when the
// repo copy is present (local checkout), the two must be identical.
const FILES = ["multiplier.json", "fbs_teams.json"];

describe("web/data mirrors repo data/", () => {
  for (const f of FILES) {
    it(`${f} matches ../data/${f} (when present)`, () => {
      const web = resolve(__dirname, "..", "data", f);
      const repo = resolve(__dirname, "..", "..", "data", f);
      expect(existsSync(web)).toBe(true);
      if (!existsSync(repo)) return; // Vercel / standalone web checkout
      expect(JSON.parse(readFileSync(web, "utf8"))).toEqual(
        JSON.parse(readFileSync(repo, "utf8")),
      );
    });
  }
});
