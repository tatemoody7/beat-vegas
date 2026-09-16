import { describe, expect, it } from "vitest";
import { gateDecision, safeNext } from "./gate";

// Public read-only (2026-09-16): GETs pass everywhere, writes need the cookie.
const base = { gateEnabled: true, misconfigured: false };

describe("gateDecision", () => {
  it("lets every safe method through without a cookie", () => {
    for (const method of ["GET", "HEAD", "OPTIONS", "get"]) {
      for (const pathname of [
        "/",
        "/results",
        "/game/401856688",
        "/api/records",
        "/logos/61.png",
      ]) {
        expect(gateDecision({ ...base, method, pathname, authed: false })).toBe(
          "next",
        );
      }
    }
  });

  it("refuses an unsigned write: 401 under /api, redirect elsewhere", () => {
    expect(
      gateDecision({
        ...base,
        method: "POST",
        pathname: "/api/picks",
        authed: false,
      }),
    ).toBe("unauthorized");
    expect(
      gateDecision({
        ...base,
        method: "PATCH",
        pathname: "/api/picks/12",
        authed: false,
      }),
    ).toBe("unauthorized");
    expect(
      gateDecision({
        ...base,
        method: "DELETE",
        pathname: "/api/picks/12",
        authed: false,
      }),
    ).toBe("unauthorized");
    expect(
      gateDecision({
        ...base,
        method: "POST",
        pathname: "/api/logout",
        authed: false,
      }),
    ).toBe("unauthorized");
    expect(
      gateDecision({
        ...base,
        method: "POST",
        pathname: "/game/1",
        authed: false,
      }),
    ).toBe("redirect");
  });

  it("lets a signed write through", () => {
    expect(
      gateDecision({
        ...base,
        method: "POST",
        pathname: "/api/picks",
        authed: true,
      }),
    ).toBe("next");
    expect(
      gateDecision({
        ...base,
        method: "DELETE",
        pathname: "/api/picks/3",
        authed: true,
      }),
    ).toBe("next");
  });

  it("fails CLOSED on everything when deployed without APP_PASSWORD", () => {
    const o = { gateEnabled: false, misconfigured: true, authed: false };
    expect(gateDecision({ ...o, method: "GET", pathname: "/" })).toBe(
      "misconfigured",
    );
    expect(gateDecision({ ...o, method: "POST", pathname: "/api/picks" })).toBe(
      "misconfigured",
    );
  });

  it("is fully open when the gate is off (local dev)", () => {
    const o = { gateEnabled: false, misconfigured: false, authed: false };
    expect(gateDecision({ ...o, method: "POST", pathname: "/api/picks" })).toBe(
      "next",
    );
  });
});

describe("safeNext", () => {
  it("accepts a same-origin path and nothing else", () => {
    expect(safeNext("/game/401856688")).toBe("/game/401856688");
    expect(safeNext("/results?week=3")).toBe("/results?week=3");
    for (const bad of [
      null,
      undefined,
      "",
      "https://evil.example",
      "//evil.example",
      "/\\evil",
      "game/1",
      "/a\nb",
    ]) {
      expect(safeNext(bad)).toBe("/");
    }
  });
});
