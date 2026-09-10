// Shared auth helpers for the app-wide password gate. Stateless: no session
// store, no database — the cookie carries its own proof. Uses Web Crypto only,
// so the same code runs in both Edge middleware and Node route handlers.
//
// THE COOKIE. `v1.<issuedAtMs>.<hmac>`, where the HMAC is over the first two
// fields under a key derived from APP_PASSWORD by PBKDF2.
//
// It used to be a bare sha256(APP_PASSWORD): the same value forever, identical
// for every device, and — because SHA-256 is fast and unsalted — an offline
// cracking target for the password itself. Anyone who saw the cookie once (a
// screenshot, a browser extension, an old laptop) had the site permanently and
// probably the password too. Three things change here:
//
//   1. PBKDF2, not a bare digest. Cracking the cookie now costs the attacker
//      ITERATIONS hashes per guess instead of one.
//   2. The cookie is a MAC, not the secret. Recovering the key from it is the
//      hard problem; the cookie itself is no longer the password in disguise.
//   3. An issued-at inside the MAC, so a stolen cookie ages out on the SERVER
//      (MAX_AGE_MS) rather than only when the thief's browser feels like
//      honouring an expiry it controls.
//
// Old-format cookies simply fail to verify, so the one upgrade cost is a single
// re-login.

export const AUTH_COOKIE = "bv_auth";

/** Cookie lifetime, enforced on both sides (Set-Cookie max-age AND the MAC). */
export const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

const VERSION = "v1";
// Fixed application salt. A per-user random salt would need somewhere to store
// it, and this gate has exactly one credential and no store; what the salt buys
// here is that the digest is specific to this app, so no precomputed SHA-256
// table applies. The work factor below is what actually resists cracking.
const SALT = new TextEncoder().encode("beat-vegas/app-gate/v1");
// Middleware runs on EVERY request, so this cannot be paid per request — the
// derived key is memoised below and the cost lands once per cold start.
const ITERATIONS = 100_000;

// Gate is OFF when APP_PASSWORD is unset (frictionless local dev).
export function gateEnabled(): boolean {
  return !!process.env.APP_PASSWORD;
}

// On Vercel (prod OR preview deploys), a missing APP_PASSWORD must fail
// CLOSED: an env-var typo or a preview environment that didn't inherit the
// var would otherwise serve the whole board — picks, ledger, edges — publicly
// with no warning. Local dev (no VERCEL env) stays open.
export function gateMisconfigured(): boolean {
  return !!process.env.VERCEL && !process.env.APP_PASSWORD;
}

const hex = (buf: ArrayBuffer): string =>
  [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");

/**
 * The signing key for a password, memoised per password value.
 *
 * PBKDF2 at 100k iterations is deliberately slow — that is the whole point —
 * so deriving it per request would put ~50ms on every page, image and API call
 * the middleware sees. Module scope survives for the life of a serverless
 * instance, so the cost is one cold start. Keyed by the password so a rotated
 * APP_PASSWORD cannot be served by a stale key.
 */
const keyCache = new Map<string, Promise<CryptoKey>>();

function signingKey(password: string): Promise<CryptoKey> {
  const cached = keyCache.get(password);
  if (cached) return cached;
  const derived = (async () => {
    const base = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(password),
      "PBKDF2",
      false,
      ["deriveBits"],
    );
    const bits = await crypto.subtle.deriveBits(
      { name: "PBKDF2", salt: SALT, iterations: ITERATIONS, hash: "SHA-256" },
      base,
      256,
    );
    return crypto.subtle.importKey(
      "raw",
      bits,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
  })();
  keyCache.set(password, derived);
  return derived;
}

async function sign(password: string, payload: string): Promise<string> {
  const key = await signingKey(password);
  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(payload),
  );
  return hex(mac);
}

/** A fresh cookie value for a correct password, or null if the gate is off. */
export async function issueToken(
  now: number = Date.now(),
): Promise<string | null> {
  const pw = process.env.APP_PASSWORD;
  if (!pw) return null;
  const payload = `${VERSION}.${now}`;
  return `${payload}.${await sign(pw, payload)}`;
}

async function sha256Hex(s: string): Promise<string> {
  return hex(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)),
  );
}

/**
 * Constant-time comparison: hash both sides to a fixed length first (no length
 * leak), then XOR every char (no early exit). Web Crypto only, so it runs in
 * Edge middleware and Node routes alike.
 */
export async function safeEqual(a: string, b: string): Promise<boolean> {
  const [ha, hb] = await Promise.all([sha256Hex(a), sha256Hex(b)]);
  let diff = 0;
  for (let i = 0; i < ha.length; i++) {
    diff |= ha.charCodeAt(i) ^ hb.charCodeAt(i);
  }
  return diff === 0;
}

/** True if `password` is the configured one. */
export async function passwordMatches(password: string): Promise<boolean> {
  const pw = process.env.APP_PASSWORD;
  if (!pw) return false;
  return safeEqual(password, pw);
}

/**
 * True if the request's cookie satisfies the gate (always true when disabled).
 *
 * A token has to be well-formed, unexpired, AND carry a MAC this deployment's
 * password can reproduce. The age check uses the signed issued-at, so it cannot
 * be edited without invalidating the MAC.
 */
export async function isAuthed(
  token: string | undefined,
  now: number = Date.now(),
): Promise<boolean> {
  const pw = process.env.APP_PASSWORD;
  if (!pw) return true; // gate disabled
  if (!token) return false;

  const parts = token.split(".");
  if (parts.length !== 3) return false; // includes every pre-v1 cookie
  const [version, issuedAt, mac] = parts;
  if (version !== VERSION) return false;

  const issued = Number(issuedAt);
  if (!Number.isFinite(issued)) return false;
  // A future issued-at is either a clock skew or a forgery attempt; a small
  // allowance keeps a slightly fast client from locking itself out.
  if (issued > now + 60_000) return false;
  if (now - issued > MAX_AGE_MS) return false;

  return safeEqual(mac, await sign(pw, `${version}.${issuedAt}`));
}
