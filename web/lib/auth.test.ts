import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  AUTH_COOKIE,
  gateEnabled,
  gateMisconfigured,
  isAuthed,
  issueToken,
  MAX_AGE_MS,
  passwordMatches,
  safeEqual,
} from "./auth";

// The password gate is the ONLY thing between the internet and the board — the
// picks, the ledger, the model's numbers — and it had no test at all. These
// pin the properties that matter, not the implementation.

const env = { ...process.env };
beforeEach(() => {
  delete process.env.APP_PASSWORD;
  delete process.env.VERCEL;
});
afterEach(() => {
  process.env = { ...env };
});

describe("the gate switches", () => {
  it("is off with no password, so local dev is frictionless", () => {
    expect(gateEnabled()).toBe(false);
    expect(gateMisconfigured()).toBe(false);
  });

  it("fails CLOSED on Vercel when APP_PASSWORD is missing", () => {
    // An env-var typo, or a preview deploy that did not inherit the var, must
    // never serve the board publicly.
    process.env.VERCEL = "1";
    expect(gateMisconfigured()).toBe(true);
  });

  it("is satisfied by anything while disabled", async () => {
    expect(await isAuthed(undefined)).toBe(true);
    expect(await isAuthed("garbage")).toBe(true);
  });
});

describe("the issued token", () => {
  beforeEach(() => {
    process.env.APP_PASSWORD = "correct horse battery staple";
  });

  it("round-trips", async () => {
    const t = await issueToken();
    expect(t).not.toBeNull();
    expect(await isAuthed(t!)).toBe(true);
  });

  it("is NOT a bare hash of the password", async () => {
    // The old cookie was literally sha256(APP_PASSWORD): one fast, unsalted
    // hash, so a leaked cookie was an offline cracking target for the password
    // itself. Anyone can compute that digest; it must not be the token.
    const digest = Array.from(
      new Uint8Array(
        await crypto.subtle.digest(
          "SHA-256",
          new TextEncoder().encode(process.env.APP_PASSWORD!),
        ),
      ),
    )
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    const t = await issueToken();
    expect(t).not.toBe(digest);
    expect(t).not.toContain(digest);
    expect(await isAuthed(digest)).toBe(false);
  });

  it("carries a signed issued-at and expires on the SERVER", async () => {
    const now = Date.now();
    const t = (await issueToken(now))!;
    expect(await isAuthed(t, now + MAX_AGE_MS - 1000)).toBe(true);
    // A thief who keeps the cookie past its life gets nothing, even though the
    // browser expiry is entirely under their control.
    expect(await isAuthed(t, now + MAX_AGE_MS + 1000)).toBe(false);
  });

  it("refuses a token whose issued-at was edited to stay fresh", async () => {
    const old = Date.now() - MAX_AGE_MS - 60_000;
    const t = (await issueToken(old))!;
    const [v, , mac] = t.split(".");
    const forged = `${v}.${Date.now()}.${mac}`; // same MAC, newer timestamp
    expect(await isAuthed(forged)).toBe(false);
  });

  it("refuses a token signed by a different password", async () => {
    const t = (await issueToken())!;
    process.env.APP_PASSWORD = "something else entirely";
    // Changing APP_PASSWORD is the break-glass revocation: every token dies.
    expect(await isAuthed(t)).toBe(false);
  });

  it("refuses malformed, empty and pre-v1 cookies", async () => {
    for (const bad of [
      undefined,
      "",
      "garbage",
      "v1.123", // too few parts
      "v1.123.abc.def", // too many
      "v2.123.abc", // unknown version
      "v1.notanumber.abc",
      "a".repeat(64), // the shape of the old cookie
    ]) {
      expect(await isAuthed(bad as string | undefined)).toBe(false);
    }
  });

  it("refuses a token issued in the future beyond clock skew", async () => {
    const now = Date.now();
    const t = (await issueToken(now + 10 * 60_000))!;
    expect(await isAuthed(t, now)).toBe(false);
  });
});

describe("password comparison", () => {
  it("accepts only the exact password", async () => {
    process.env.APP_PASSWORD = "hunter2";
    expect(await passwordMatches("hunter2")).toBe(true);
    expect(await passwordMatches("hunter")).toBe(false);
    expect(await passwordMatches("hunter22")).toBe(false);
    expect(await passwordMatches("")).toBe(false);
  });

  it("never matches when no password is configured", async () => {
    expect(await passwordMatches("anything")).toBe(false);
    expect(await passwordMatches("")).toBe(false);
  });

  it("compares equal-length-independently (no length leak)", async () => {
    // safeEqual hashes both sides first, so a one-character password and a
    // thousand-character guess take the same comparison path.
    expect(await safeEqual("a", "a")).toBe(true);
    expect(await safeEqual("a", "b".repeat(1000))).toBe(false);
  });
});

it("the cookie name is stable", () => {
  // Renaming it silently logs everyone out; that should be a deliberate act.
  expect(AUTH_COOKIE).toBe("bv_auth");
});
