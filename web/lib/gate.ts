// The password gate's DECISION, as a pure function so middleware.ts stays a
// thin adapter and the rule is unit-tested (lib/gate.test.ts).
//
// Public read-only (Tate, 2026-09-16): every page and every GET is open, so a
// friend with the link sees the board, Results and Track record. The password
// guards WRITES only — logging, editing and deleting picks — which are the
// only requests that use an unsafe method. The pick routes ALSO check the
// cookie themselves (lib/session.ts::requireAuth), so a future matcher edit
// cannot open the ledger by accident.

export type GateDecision =
  "misconfigured" | "next" | "unauthorized" | "redirect";

/** Methods that never change state; RFC 9110 §9.2.1. */
export const SAFE_METHODS: ReadonlySet<string> = new Set([
  "GET",
  "HEAD",
  "OPTIONS",
]);

export function gateDecision(o: {
  method: string;
  pathname: string;
  authed: boolean;
  gateEnabled: boolean;
  misconfigured: boolean;
}): GateDecision {
  // Deployed on Vercel without APP_PASSWORD: fail closed on EVERYTHING. The
  // pages would be fine open, but the write routes would not, and a 503 that
  // says why is louder than a ledger anyone can post to.
  if (o.misconfigured) return "misconfigured";
  if (!o.gateEnabled) return "next";
  if (SAFE_METHODS.has(o.method.toUpperCase())) return "next";
  if (o.authed) return "next";
  return o.pathname.startsWith("/api/") ? "unauthorized" : "redirect";
}

/**
 * Where /login sends the browser afterwards. Only a same-origin PATH is
 * accepted ("/game/401856688"); anything else — an absolute URL, a
 * protocol-relative "//evil", a backslash trick, an empty value — falls back
 * to the board. Open redirects are the classic mistake with a `next` param.
 */
export function safeNext(raw: string | null | undefined): string {
  if (!raw) return "/";
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\"))
    return "/";
  if (/[\x00-\x1f]/.test(raw)) return "/";
  return raw;
}
