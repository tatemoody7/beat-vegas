import { describe, expect, it } from "vitest";
import { laneFor } from "./prisma";

// Prisma 7 requires a driver adapter on every client. The one thing this
// migration could silently break is WHICH adapter a given environment gets:
// the Neon serverless driver cannot reach the local sandbox, and node-postgres
// hangs on the campus network. Pin the rule.
describe("the driver adapter lane follows NEON_HTTP", () => {
  const neon =
    "postgresql://u:p@ep-x-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require";
  it("NEON_HTTP=1 with a postgres URL takes the Neon HTTPS/WebSocket lane", () => {
    expect(laneFor({ DATABASE_URL: neon, NEON_HTTP: "1" })).toBe("neon-http");
  });
  it("production (flag unset) and the local sim take node-postgres", () => {
    expect(laneFor({ DATABASE_URL: neon })).toBe("pg");
    expect(
      laneFor({ DATABASE_URL: "postgresql://localhost:5433/beatvegas_sim" }),
    ).toBe("pg");
    expect(
      laneFor({
        DATABASE_URL: "postgresql://localhost:5433/x",
        NEON_HTTP: "0",
      }),
    ).toBe("pg");
  });
  it("the flag alone is not enough — a non-postgres URL stays on pg", () => {
    expect(
      laneFor({ DATABASE_URL: "file:../../data/demo.db", NEON_HTTP: "1" }),
    ).toBe("pg");
    expect(laneFor({ NEON_HTTP: "1" })).toBe("pg");
  });
});

// Prisma 7's adapter pulls `pg` (dns/net/tls) into whatever bundle imports the
// client. A "use client" component that imports a VALUE from a prisma-backed
// module therefore breaks the browser build outright -- app/components/PicksList
// did exactly that through lib/picks::isOffPolicy, and every page that renders it
// 500'd. Type-only imports are erased and stay fine.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const DB_BACKED = [
  "picks",
  "board",
  "proof",
  "records",
  "movement",
  "lineCheck",
  "postmortem",
  "preview",
  "decision-quality",
  "lineStudy",
  "rulePause",
  "homeBoard",
  "prisma",
  "ledger",
  "weeklyReview",
];

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return tsxFiles(p);
    return p.endsWith(".tsx") || p.endsWith(".ts") ? [p] : [];
  });
}

describe("no client component imports a value from a database-backed module", () => {
  it("holds across app/", () => {
    const offenders: string[] = [];
    for (const file of tsxFiles(join(import.meta.dirname, "..", "app"))) {
      const src = readFileSync(file, "utf8");
      if (!/^\s*["']use client["']/m.test(src)) continue;
      for (const m of src.matchAll(
        /import\s+(type\s+)?([^;]*?)from\s+["']@\/lib\/([\w-]+)["']/g,
      )) {
        const [, typeOnly, clause, mod] = m;
        if (!DB_BACKED.includes(mod)) continue;
        // `import type {...}` and an all-`type` named clause are erased.
        if (typeOnly) continue;
        const names = clause
          .replace(/[{}]/g, "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
        const values = names.filter((n) => !n.startsWith("type "));
        if (values.length)
          offenders.push(
            `${file.split("/web/")[1]} imports ${values.join(", ")} from @/lib/${mod}`,
          );
      }
    }
    expect(offenders).toEqual([]);
  });
});
