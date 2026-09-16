import { PrismaClient } from "@prisma/client";
import { neonConfig, Pool } from "@neondatabase/serverless";
import { PrismaNeon } from "@prisma/adapter-neon";
import ws from "ws";

// Singleton — avoids exhausting connections during Next.js dev hot-reload.
const globalForPrisma = globalThis as unknown as {
  prisma?: PrismaClient;
  warnedProd?: boolean;
};

/**
 * NEON_HTTP=1 (web/.env, local only): reach Neon over HTTPS/WebSockets on
 * port 443 through Prisma's Neon driver adapter instead of raw Postgres on
 * 5432. Some networks (the campus network) let a 5432 connection open and then
 * drop the TLS data, so the plain client hangs with "Can't reach database
 * server". Production on Vercel keeps the plain TCP client (flag unset).
 */
function makeClient(): PrismaClient {
  const url = process.env.DATABASE_URL ?? "";
  if (process.env.NEON_HTTP === "1" && url.startsWith("postgres")) {
    neonConfig.webSocketConstructor = ws;
    neonConfig.poolQueryViaFetch = true;
    const pool = new Pool({ connectionString: url });
    return new PrismaClient({ adapter: new PrismaNeon(pool) });
  }
  return new PrismaClient();
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
