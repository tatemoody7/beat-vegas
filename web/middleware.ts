import { NextRequest, NextResponse } from "next/server";
import { cronGate } from "@/lib/gate";

// READ-ONLY RESEARCH RECORD since 2026-10-18 (final-2026 plan, D17): every
// page and every route is public, there is no password and no cookie, and the
// only request that needs a lock is Vercel's cron tick on /api/cron/[job],
// which carries CRON_SECRET as a bearer token. The route checks the same
// secret itself; this is the outer wall, so a future matcher edit cannot open
// the dispatch button by accident. The rule is lib/gate.ts::cronGate.
export async function middleware(req: NextRequest) {
  const decision = await cronGate({
    authorization: req.headers.get("authorization"),
    secret: process.env.CRON_SECRET,
  });
  switch (decision) {
    case "misconfigured":
      return NextResponse.json(
        { error: "CRON_SECRET not configured" },
        { status: 500 },
      );
    case "unauthorized":
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    case "next":
      return NextResponse.next();
  }
}

export const config = {
  matcher: ["/api/cron/:path*"],
};
