import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import teamLogos from "@/data/team_logos.json";
import { logoSchool, logoSrc } from "./teamLogos";

// The index and the vendored files must agree in BOTH directions. An id in the
// index with no file renders a broken image on the board; a file with no index
// entry is dead weight nothing can reach. Either one means a half-finished
// scripts/fetch_team_logos.py run, and this is where that gets caught.

const LOGO_DIR = join(process.cwd(), "public", "logos");
const INDEX: Record<string, string> = teamLogos;

describe("teamLogos", () => {
  it("has a vendored file for every id in the index", () => {
    const missing = Object.keys(INDEX).filter(
      (id) => !existsSync(join(LOGO_DIR, `${id}.png`)),
    );
    expect(missing).toEqual([]);
  });

  it("has an index entry for every vendored file", () => {
    const orphans = readdirSync(LOGO_DIR)
      .filter((f) => f.endsWith(".png"))
      .map((f) => f.replace(/\.png$/, ""))
      .filter((id) => INDEX[id] === undefined);
    expect(orphans).toEqual([]);
  });

  it("covers the FBS teams the board is actually made of", () => {
    // Alabama, Kansas State, Florida, Missouri — the ids CFBD keys logos on are
    // the same ids games.home_team_id already stores.
    expect(logoSrc(333)).toBe("/logos/333.png");
    expect(logoSchool(2306)).toBe("Kansas State");
    expect(logoSrc(57)).toBe("/logos/57.png");
    expect(logoSrc(142)).toBe("/logos/142.png");
  });

  it("returns null rather than a path when there is no artwork", () => {
    // 495 is Bluefield: in the games table as an opponent, no logo anywhere.
    expect(logoSrc(495)).toBeNull();
    expect(logoSrc(null)).toBeNull();
    expect(logoSrc(undefined)).toBeNull();
    expect(logoSchool(495)).toBeNull();
  });
});
