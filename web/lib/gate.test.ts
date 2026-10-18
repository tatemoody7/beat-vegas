import { describe, expect, it } from "vitest";
import { cronGate, safeEqual } from "./gate";

// The one lock left (2026-10-18, D17): the cron route's bearer secret.
describe("cronGate", () => {
  const secret = "s3cret-value";

  it("fails closed when CRON_SECRET is not configured, whatever the header", async () => {
    expect(
      await cronGate({ authorization: `Bearer ${secret}`, secret: undefined }),
    ).toBe("misconfigured");
    expect(await cronGate({ authorization: null, secret: "" })).toBe(
      "misconfigured",
    );
  });

  it("refuses a missing, malformed or wrong bearer token", async () => {
    expect(await cronGate({ authorization: null, secret })).toBe(
      "unauthorized",
    );
    expect(await cronGate({ authorization: secret, secret })).toBe(
      "unauthorized",
    );
    expect(await cronGate({ authorization: "Bearer nope", secret })).toBe(
      "unauthorized",
    );
    expect(await cronGate({ authorization: "Basic abc", secret })).toBe(
      "unauthorized",
    );
  });

  it("lets the configured secret through", async () => {
    expect(await cronGate({ authorization: `Bearer ${secret}`, secret })).toBe(
      "next",
    );
  });
});

describe("safeEqual", () => {
  it("compares whole strings, lengths included", async () => {
    expect(await safeEqual("abc", "abc")).toBe(true);
    expect(await safeEqual("abc", "abd")).toBe(false);
    expect(await safeEqual("abc", "abcd")).toBe(false);
    expect(await safeEqual("", "")).toBe(true);
  });
});
