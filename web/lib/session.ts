import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE, gateEnabled, isAuthed } from "@/lib/auth";

// Server-side view of "is this visitor signed in?". Pages use it to decide
// whether to show Lock or Unlock and whether the log-pick form is offered;
// the pick routes use requireAuth so a write is refused even if the
// middleware matcher ever stops covering them.

/** True when the gate is off (local dev) or the request carries a valid cookie. */
export async function viewerIsAuthed(): Promise<boolean> {
  if (!gateEnabled()) return true;
  const jar = await cookies();
  return isAuthed(jar.get(AUTH_COOKIE)?.value);
}

/** 401 JSON when the request is not signed in; null when it may proceed. */
export async function requireAuth(
  req: NextRequest,
): Promise<NextResponse | null> {
  if (!gateEnabled()) return null;
  if (await isAuthed(req.cookies.get(AUTH_COOKIE)?.value)) return null;
  return NextResponse.json(
    { error: "unauthorized — unlock to log picks" },
    { status: 401 },
  );
}
