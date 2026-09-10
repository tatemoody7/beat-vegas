import { NextRequest, NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  gateEnabled,
  issueToken,
  MAX_AGE_MS,
  passwordMatches,
} from "@/lib/auth";

// POST /api/login { password } — sets the auth cookie on a correct password.
//
// This and /api/health are the only endpoints reachable without the cookie, so
// this is the front door for anyone on the internet. The comparison is
// constant-time, which closes the timing channel but says nothing about VOLUME:
// before the throttle below there was nothing at all stopping a script from
// grinding the password at whatever rate Vercel would serve.

/**
 * Per-instance sliding-window throttle.
 *
 * Honest about what this is: serverless instances do not share memory, so a
 * distributed attacker gets ATTEMPTS tries per instance rather than per site,
 * and a cold start resets the window. It is a speed bump, not a lockout — the
 * durable version needs Redis/KV, which is a new dependency in the request path
 * for a single-user site. What it does buy is real: it turns "unlimited guesses
 * per second" into a rate low enough that a wordlist run stops being practical,
 * and it costs nothing.
 */
const WINDOW_MS = 15 * 60 * 1000;
const ATTEMPTS = 10;
const attempts = new Map<string, number[]>();

function throttled(ip: string, now: number): boolean {
  const recent = (attempts.get(ip) ?? []).filter((t) => now - t < WINDOW_MS);
  if (recent.length >= ATTEMPTS) {
    attempts.set(ip, recent);
    return true;
  }
  recent.push(now);
  attempts.set(ip, recent);
  // Bound the map so a rotating-IP attacker cannot grow it without limit.
  if (attempts.size > 5_000) {
    for (const [k, v] of attempts) {
      if (v.every((t) => now - t >= WINDOW_MS)) attempts.delete(k);
    }
  }
  return false;
}

function clientIp(req: NextRequest): string {
  // Vercel sets x-forwarded-for; the first entry is the real client.
  const fwd = req.headers.get("x-forwarded-for");
  return (
    fwd?.split(",")[0]?.trim() || req.headers.get("x-real-ip") || "unknown"
  );
}

export async function POST(req: NextRequest) {
  if (!gateEnabled()) return NextResponse.json({ ok: true }); // gate disabled

  if (throttled(clientIp(req), Date.now())) {
    return NextResponse.json(
      { error: "too many attempts — wait a few minutes" },
      { status: 429 },
    );
  }

  let password: unknown;
  try {
    ({ password } = await req.json());
  } catch {
    password = undefined;
  }
  const ok = typeof password === "string" && (await passwordMatches(password));
  if (!ok) {
    return NextResponse.json({ error: "incorrect password" }, { status: 401 });
  }

  const token = await issueToken();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, token!, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    // Matches the age the token itself carries, so the browser and the server
    // agree on when it dies rather than only the browser deciding.
    maxAge: MAX_AGE_MS / 1000,
  });
  return res;
}
