import { PrismaClient } from "@prisma/client";
import { neonConfig } from "@neondatabase/serverless";
import { PrismaNeon } from "@prisma/adapter-neon";
import { PrismaPg } from "@prisma/adapter-pg";
import ws from "ws";

// Singleton — avoids exhausting connections during Next.js dev hot-reload.
const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
  warnedProd?: boolean;
};

/**
 * Prisma 7: every client carries a driver adapter; the Rust-engine TCP client
 * is gone. Two lanes, chosen by environment:
 *
 * - NEON_HTTP=1 (web/.env, local only): reach Neon over HTTPS/WebSockets on
 *   port 443 through the Neon serverless driver. Some networks (the campus
 *   network) let a 5432 connection open and then drop the TLS data, so a plain
 *   Postgres client hangs with "Can't reach database server". The Neon adapter
 *   only speaks Neon's proxy, so it cannot reach the local sandbox.
 * - otherwise: node-postgres (`pg`) over TCP — Vercel production against Neon,
 *   and `next dev` against the local sim (scripts/simulate_week.py).
 *
 * `lanes()` is exported for lib/prisma.test.ts, which pins the choice: this is
 * the one thing the Prisma 7 migration could silently get wrong.
 */
export type Lane = "neon-http" | "pg";

export function laneFor(env: {
  DATABASE_URL?: string | undefined;
  NEON_HTTP?: string | undefined;
  [k: string]: string | undefined;
}): Lane {
  const url = env.DATABASE_URL ?? "";
  return env.NEON_HTTP === "1" && url.startsWith("postgres")
    ? "neon-http"
    : "pg";
}

function makeClient(): PrismaClient {
  const url = process.env.DATABASE_URL ?? "";
  if (laneFor(process.env) === "neon-http") {
    neonConfig.webSocketConstructor = ws;
    neonConfig.poolQueryViaFetch = true;
    return new PrismaClient({
      adapter: new PrismaNeon({ connectionString: url }),
    });
  }
  return new PrismaClient({ adapter: new PrismaPg({ connectionString: url }) });
}

export const prisma = globalForPrisma.prisma ?? makeClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
  // A dev server pointed at PRODUCTION Neon is what exhausted the Free plan's
  // 5 GB/month egress on 2026-09-16: every save, refresh and screenshot pass
  // through the redesign sprint was a full board render against the live
  // database. Warn once per process; never block (a deliberate read of prod
  // from a laptop is sometimes the point). scripts/simulate_week.py gives a
  // local Postgres for everything else — see web/.env.example.
  const url = process.env.DATABASE_URL ?? "";
  if (url.includes("neon.tech") && !globalForPrisma.warnedProd) {
    globalForPrisma.warnedProd = true;
    console.warn(
      "[prisma] DATABASE_URL points at Neon (production) from a development " +
        "server. Every render is metered egress; prefer the local sandbox " +
        "(python scripts/simulate_week.py) unless you mean to read prod.",
    );
  }
}
