import { NextRequest, NextResponse } from "next/server";
import { getLineCheck } from "@/lib/lineCheck";
import {
  parseRefreshBody,
  REFRESH_COOLDOWN_MIN,
  REFRESH_CREDIT_FLOOR,
  REFRESH_DISPATCH_URL,
  refreshDispatchBody,
  refreshKey,
} from "@/lib/priceRefresh";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/session";
import { staleAt } from "@/lib/ticketPolicy";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// POST /api/price-refresh {gameId} — poll ONE game's Hard Rock first-half
// price now (lib/priceRefresh.ts). Owner-only (the cookie, here and in
// middleware). It spends an Odds API credit, so every refusal comes first:
// unknown or kicked-off game, a price already fresh, a low credit gauge, a
// request inside the cooldown. The GitHub token is the one /api/cron uses.

const TIMEOUT_MS = 8_000;

const out = (status: number, body: Record<string, unknown>) =>
  NextResponse.json(body, { status });

export async function POST(req: NextRequest) {
  const denied = await requireAuth(req);
  if (denied) return denied;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return out(400, { error: "invalid JSON body" });
  }
  const parsed = parseRefreshBody(body);
  if (!parsed.ok) return out(400, { error: parsed.error });
  const { gameId } = parsed;
  const now = new Date();

  let game: { season: number; start_date: Date | null } | null;
  let seenAt: string | null = null;
  let credits: number | null = null;
  try {
    game = await prisma.games.findUnique({
      where: { id: gameId },
      select: { season: true, start_date: true },
    });
    if (game) {
      const rows = await getLineCheck(game.season, "1h");
      seenAt = rows.find((r) => r.gameId === gameId)?.hrSeenAt ?? null;
      const g = await prisma.$queryRaw<{ value: string }[]>`
        SELECT value FROM app_settings WHERE key = 'odds_credits_remaining'`;
      const n = Number(g[0]?.value);
      credits = g[0] && Number.isFinite(n) ? n : null;
    }
  } catch (e) {
    console.error("[price-refresh] lookup failed:", e);
    return out(503, {
      error: "could not reach the database — nothing was requested",
    });
  }
  if (!game) return out(404, { error: "That game is not on file." });
  if (game.start_date !== null && game.start_date <= now) {
    return out(409, { error: "That game has already kicked off." });
  }
  if (seenAt !== null && !staleAt(seenAt, now)) {
    return out(409, {
      error:
        "Hard Rock’s price was confirmed in the last 6 hours — nothing to refresh. Log the ticket.",
    });
  }
  // An unknown gauge does not block: the poll itself stops at the same floor
  // (poll_lines --credit-floor). A KNOWN low gauge refuses before dispatching.
  if (credits !== null && credits < REFRESH_CREDIT_FLOOR) {
    return out(409, {
      error: `Odds API credits are down to ${credits}; refreshes stop below ${REFRESH_CREDIT_FLOOR} so the scheduled closes keep their budget.`,
    });
  }

  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    console.error("[price-refresh] GITHUB_DISPATCH_TOKEN is not configured");
    return out(500, { error: "The refresh trigger is not configured." });
  }

  // THE COOLDOWN, claimed atomically: the upsert writes only when no request
  // for this game landed in the last REFRESH_COOLDOWN_MIN minutes, so two
  // clicks, two tabs or two Vercel instances dispatch once. RETURNING says
  // whether this request won the claim.
  const key = refreshKey(gameId);
  const stamp = now.toISOString().slice(0, 19);
  let claimed: { key: string }[];
  try {
    claimed = await prisma.$queryRaw<{ key: string }[]>`
      INSERT INTO app_settings (key, value, note, updated_at)
      VALUES (${key}, ${stamp}, 'requested', ${stamp}::timestamp)
      ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = EXCLUDED.updated_at
        WHERE app_settings.updated_at IS NULL
           OR app_settings.updated_at < EXCLUDED.updated_at - make_interval(mins => ${REFRESH_COOLDOWN_MIN})
      RETURNING key`;
  } catch (e) {
    console.error("[price-refresh] cooldown claim failed:", e);
    return out(503, {
      error: "could not reach the database — nothing was requested",
    });
  }
  if (claimed.length === 0) {
    return out(429, {
      error: `A refresh for this game was requested in the last ${REFRESH_COOLDOWN_MIN} minutes. Its price lands in about 1–2 minutes; log the ticket again then.`,
    });
  }

  const release = async () => {
    try {
      await prisma.$executeRaw`DELETE FROM app_settings WHERE key = ${key} AND value = ${stamp}`;
    } catch (e) {
      console.error("[price-refresh] could not release the cooldown:", e);
    }
  };
  let resp: Response;
  try {
    resp = await fetch(REFRESH_DISPATCH_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "beat-vegas-price-refresh",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(refreshDispatchBody(gameId)),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    await release();
    console.error("[price-refresh] dispatch request failed:", e);
    return out(502, {
      error: "Could not reach GitHub to request the refresh. Try again.",
    });
  }
  if (resp.status !== 204 && resp.status !== 200) {
    await release();
    const detail = (await resp.text().catch(() => "")).slice(0, 200);
    console.error(`[price-refresh] dispatch ${resp.status}: ${detail}`);
    return out(502, {
      error: "GitHub refused the refresh request. Try again later.",
    });
  }
  console.log(
    JSON.stringify({ tag: "price-refresh", gameId, dispatched: true }),
  );
  return out(202, {
    ok: true,
    message:
      "Refresh requested. Hard Rock’s price lands in about 1–2 minutes; log the ticket again then.",
  });
}
