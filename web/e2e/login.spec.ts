import { expect, test } from "@playwright/test";
import { E2E_PASSWORD } from "./helpers/env";

// The gate: every page and every GET is public; the password guards WRITES
// (lib/gate.ts::gateDecision, plus lib/session.ts::requireAuth inside each pick
// route). The header says which side of it the visitor is on.
//
// /api/login throttles at 10 attempts per 15 minutes per IP and the counter
// lives in the server process, so this file spends exactly TWO attempts (one
// wrong, one right) and only on the desktop project; the setup project spent
// the third. Running the suite three times inside a quarter of an hour stays
// under the limit.

const PUBLIC_GETS = [
  "/",
  "/results",
  "/proof",
  "/proof/records",
  "/game/900001",
  "/api/health",
];

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("every page and every GET is public", async ({ request }) => {
    for (const path of PUBLIC_GETS) {
      const res = await request.get(path);
      expect(res.status(), path).toBe(200);
    }
  });

  test("writes are refused with a 401 before any body is read", async ({
    request,
  }) => {
    const post = await request.post("/api/picks", {
      data: { gameId: 900002, line: 53.5, price: -110 },
    });
    expect(post.status()).toBe(401);
    expect(await post.json()).toEqual({ error: "unauthorized" });
    expect((await request.patch("/api/picks/1", { data: {} })).status()).toBe(
      401,
    );
    expect((await request.delete("/api/picks/1")).status()).toBe(401);
    expect((await request.post("/api/logout")).status()).toBe(401);
  });

  test("the header offers Unlock", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Unlock" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Lock" })).toHaveCount(0);
  });

  test("the game page offers the way in, and remembers the game", async ({
    page,
  }) => {
    await page.goto("/game/900002");
    const link = page.getByRole("link", { name: "Unlock to log a pick" });
    await expect(link).toBeVisible();
    expect(await link.getAttribute("href")).toBe(
      `/login?next=${encodeURIComponent("/game/900002")}`,
    );
    await expect(
      page.getByRole("button", { name: /Log this bet/ }),
    ).toHaveCount(0);
  });

  test("a wrong password is a 401 and the form says so", async ({
    page,
    isMobile,
  }) => {
    test.skip(isMobile, "one attempt per run: the desktop project spends it");
    await page.goto("/login");
    await page.getByPlaceholder("Password").fill("not-the-password");
    const [res] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith("/api/login")),
      page.getByRole("button", { name: "Unlock" }).click(),
    ]);
    expect(res.status()).toBe(401);
    expect(await res.json()).toEqual({ error: "incorrect password" });
    // The form's own <p role="alert">; Next mounts a route announcer with the
    // same role, so getByRole("alert") is ambiguous here.
    await expect(page.locator('p[role="alert"]')).toHaveText("Wrong password.");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("the right password returns to ?next=, Lock appears, and Lock signs out", async ({
    page,
    isMobile,
  }) => {
    test.skip(isMobile, "one attempt per run: the desktop project spends it");
    await page.goto(`/login?next=${encodeURIComponent("/game/900002")}`);
    await page.getByPlaceholder("Password").fill(E2E_PASSWORD);
    await page.getByRole("button", { name: "Unlock" }).click();
    await page.waitForURL("**/game/900002");
    await expect(page.getByRole("button", { name: "Lock" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Log this bet" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Lock" }).click();
    await page.waitForURL("**/login");
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Unlock" })).toBeVisible();
    // The cookie is gone, not just hidden: a write is refused again.
    const post = await page.request.post("/api/picks", {
      data: { gameId: 900002, line: 53.5, price: -110 },
    });
    expect(post.status()).toBe(401);
  });
});

test.describe("signed in (the setup project's cookie)", () => {
  test("the header offers Lock and the game page offers the log button", async ({
    page,
  }) => {
    await page.goto("/game/900002");
    await expect(page.getByRole("button", { name: "Lock" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Unlock" })).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Log this bet" }),
    ).toBeVisible();
  });

  test("a write reaches validation instead of the gate", async ({
    request,
  }) => {
    // Missing line: parsePickBody rejects it with a 400 -- proof the request got
    // past requireAuth and the middleware.
    const res = await request.post("/api/picks", { data: { gameId: 900002 } });
    expect(res.status()).toBe(400);
    expect(await res.json()).toEqual({ error: "Enter the first-half total." });
  });
});
