import { expect, test } from "@playwright/test";

// The eleven routes the 2026-09-10 restructure moved are `next.config.ts`
// redirects with `permanent: true`: a 308 (never a 307 -- that is what a
// redirect() page body sends, and browsers do not cache it), the destination
// in `location`, and the query string carried across because none of the rules
// uses `has`.

const MOVED: [string, string][] = [
  ["/board", "/"],
  ["/preview", "/"],
  ["/line-check", "/"],
  ["/movement", "/"],
  ["/ledger", "/results"],
  ["/picks", "/results"],
  ["/weekly-review", "/results"],
  ["/line-study", "/proof"],
  ["/research", "/proof"],
  ["/research/records", "/proof/records"],
  ["/glossary", "/proof#glossary"],
];

const pathOf = (location: string): string => {
  // `location` may be absolute or relative; compare path + query + hash only.
  const u = new URL(location, "http://e2e.invalid");
  return `${u.pathname}${u.search}${u.hash}`;
};

for (const [from, to] of MOVED) {
  test(`${from} → ${to} is a 308`, async ({ request }) => {
    const res = await request.get(from, { maxRedirects: 0 });
    expect(res.status()).toBe(308);
    expect(pathOf(res.headers().location)).toBe(to);
  });
}

test("a moved route keeps its query string", async ({ request }) => {
  const res = await request.get("/board?season=2025&week=7", {
    maxRedirects: 0,
  });
  expect(res.status()).toBe(308);
  const loc = new URL(res.headers().location, "http://e2e.invalid");
  expect(loc.pathname).toBe("/");
  expect(loc.searchParams.get("season")).toBe("2025");
  expect(loc.searchParams.get("week")).toBe("7");
});

test("the three tabs and the game route are not redirects", async ({
  request,
}) => {
  for (const path of ["/", "/results", "/proof", "/proof/records", "/login"]) {
    const res = await request.get(path, { maxRedirects: 0 });
    expect(res.status(), path).toBe(200);
  }
});
