import { NextRequest, NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  gateEnabled,
  gateMisconfigured,
  isAuthed,
} from "@/lib/auth";
import { gateDecision } from "@/lib/gate";

// PUBLIC READ-ONLY since 2026-09-16: every page and every GET is open, so the
// link can be shared. The password guards writes — POST/PATCH/DELETE on the
// pick routes (401 for /api/*, redirect to /login for a browser form). The
// rule itself is lib/gate.ts::gateDecision, unit-tested; this is the adapter.
//
// /login + /api/login + static assets are exempt via the matcher below — and
// so is /api/cron, which Vercel's scheduler calls with no session cookie. That
// route authenticates itself against CRON_SECRET and fails closed when unset.
export async function middleware(req: NextRequest) {
  const token = req.cookies.get(AUTH_COOKIE)?.value;
  const decision = gateDecision({
    method: req.method,
    pathname: req.nextUrl.pathname,
    gateEnabled: gateEnabled(),
    misconfigured: gateMisconfigured(),
    // Only evaluated when it can matter (an unsafe method with the gate on):
    // the PBKDF2 key is memoised, but the MAC is still per request.
    authed:
      gateEnabled() &&
      !gateMisconfigured() &&
      req.method !== "GET" &&
      req.method !== "HEAD"
        ? await isAuthed(token)
        : false,
  });
  switch (decision) {
    case "misconfigured":
      // Deployed without APP_PASSWORD: fail closed, never serve a ledger anyone can post to.
      return new NextResponse(
        "APP_PASSWORD is not configured for this deployment.",
        { status: 503 },
      );
    case "next":
      return NextResponse.next();
    case "unauthorized":
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    case "redirect": {
      const url = req.nextUrl.clone();
      url.pathname = "/login";
      url.search = "";
      return NextResponse.redirect(url);
    }
  }
}

// The exemptions are ANCHORED — `api/login$` and `api/login/`, not a bare
// `api/login` prefix. Unanchored, a future `/api/loginhelper`, `/api/healthz`
// or `/api/cronjobs` would be public the moment it was added, with nothing in
// the diff to say so. Nothing matches those today; this is about the next route
// someone writes.
export const config = {
  matcher: [
    "/((?!api/login(?:/|$)|api/health(?:/|$)|api/cron(?:/|$)|login(?:/|$)|_next/static/|_next/image(?:/|\\?|$)|favicon.ico$).*)",
  ],
};
