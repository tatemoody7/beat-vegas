import { expect, test } from "@playwright/test";

// The write path is GONE (final-2026 plan, D2/D16/D17, 2026-10-18): no pick is
// logged, edited or deleted from the site, there is no bet CSV, no login and no
// price refresh. A route that no longer exists answers 404, so a stale
// bookmark or script can never reach the frozen ledger again.

test("the pick, bet, login and price-refresh routes are gone (404)", async ({
  request,
}) => {
  const gone: [string, "get" | "post" | "patch" | "delete"][] = [
    ["/api/picks", "post"],
    ["/api/picks/1", "patch"],
    ["/api/picks/1", "delete"],
    ["/api/bets?season=2026", "get"],
    ["/api/login", "post"],
    ["/api/logout", "post"],
    ["/api/price-refresh", "post"],
    ["/login", "get"],
  ];
  for (const [path, method] of gone) {
    const res = await request[method](path, {
      data: method === "get" ? undefined : { gameId: 900002, line: 53.5 },
      maxRedirects: 0,
    });
    expect(res.status(), `${method.toUpperCase()} ${path}`).toBe(404);
  }
});
