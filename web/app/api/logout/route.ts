import { NextResponse } from "next/server";
import { AUTH_COOKIE } from "@/lib/auth";

// POST /api/logout — clears the auth cookie.
//
// Client-side only: the token is stateless, so there is nothing server-side to
// revoke. What limits a token that got away is the signed issued-at in it
// (lib/auth.ts MAX_AGE_MS); changing APP_PASSWORD invalidates every token at
// once, which is the break-glass move.
export async function POST() {
  const res = NextResponse.json({ ok: true });
  // The attributes must MATCH the ones login set, or a browser can treat this
  // as a different cookie and leave the original in place. `secure` was the one
  // missing here: a Secure cookie is not necessarily cleared by a non-Secure
  // Set-Cookie of the same name.
  res.cookies.set(AUTH_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  });
  return res;
}
