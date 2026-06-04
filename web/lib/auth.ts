// Shared auth helpers for the app-wide password gate. Stateless: the cookie
// holds sha256(APP_PASSWORD), never the raw password. Uses Web Crypto so the
// same code runs in both Edge middleware and Node route handlers.

export const AUTH_COOKIE = "bv_auth";

// Gate is OFF when APP_PASSWORD is unset (frictionless local dev).
export function gateEnabled(): boolean {
  return !!process.env.APP_PASSWORD;
}

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(s),
  );
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// The expected cookie token, or null if the gate is disabled.
export async function expectedToken(): Promise<string | null> {
  const pw = process.env.APP_PASSWORD;
  return pw ? sha256Hex(pw) : null;
}

// True if the request's cookie satisfies the gate (always true when disabled).
export async function isAuthed(token: string | undefined): Promise<boolean> {
  const expected = await expectedToken();
  if (expected === null) return true;
  return !!token && token === expected;
}
