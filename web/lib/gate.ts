// The one lock left on the site (final-2026 plan, decision D17, 2026-10-18):
// `/api/cron/[job]` is called by Vercel's scheduler with a bearer token that
// must equal CRON_SECRET. Every page and every other route is public and
// read-only; the password gate, its cookie and `/login` are gone, because no
// write path remains for them to guard. Pure, so middleware.ts stays a thin
// adapter and the rule is unit-tested (lib/gate.test.ts). Web Crypto only: the
// same code runs in Edge middleware and in a Node route handler.

export type CronGateDecision = "misconfigured" | "unauthorized" | "next";

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(s),
  );
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Constant-time string compare. Both sides are hashed to a fixed width first,
 *  so a length mismatch never returns early and leaks the secret's length. */
export async function safeEqual(a: string, b: string): Promise<boolean> {
  const [ha, hb] = await Promise.all([sha256Hex(a), sha256Hex(b)]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) {
    diff |= ha.charCodeAt(i) ^ hb.charCodeAt(i);
  }
  return diff === 0;
}

/**
 * Whether a cron request may proceed. FAILS CLOSED when the secret is not
 * configured: a 200 there would read as a routine no-op in the dashboard while
 * the route sat open as a public button that spends Odds API credits.
 */
export async function cronGate(o: {
  authorization: string | null;
  secret: string | undefined;
}): Promise<CronGateDecision> {
  if (!o.secret) return "misconfigured";
  const header = o.authorization ?? "";
  if (!header.startsWith("Bearer ")) return "unauthorized";
  return (await safeEqual(header.slice(7), o.secret)) ? "next" : "unauthorized";
}
