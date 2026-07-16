import { NextRequest, NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  gateEnabled,
  gateMisconfigured,
  isAuthed,
} from "@/lib/auth";

// Locks the whole app when APP_PASSWORD is set: browser requests redirect to
// /login, API requests get 401. /login + /api/login + static assets are exempt
// via the matcher below.
export async function middleware(req: NextRequest) {
  if (gateMisconfigured()) {
    // Deployed without APP_PASSWORD: fail closed, never serve the board open.
    return new NextResponse(
      "APP_PASSWORD is not configured for this deployment.",
      { status: 503 },
    );
  }
  if (!gateEnabled()) return NextResponse.next();

  const token = req.cookies.get(AUTH_COOKIE)?.value;
  if (await isAuthed(token)) return NextResponse.next();

  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: [
    "/((?!api/login|api/health|login|_next/static|_next/image|favicon.ico).*)",
  ],
};
