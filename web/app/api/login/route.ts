import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE, expectedToken, gateEnabled } from "@/lib/auth";

// POST /api/login { password } — sets the auth cookie on a correct password.
export async function POST(req: NextRequest) {
  if (!gateEnabled()) return NextResponse.json({ ok: true }); // gate disabled

  let password: unknown;
  try {
    ({ password } = await req.json());
  } catch {
    password = undefined;
  }
  if (password !== process.env.APP_PASSWORD) {
    return NextResponse.json({ error: "incorrect password" }, { status: 401 });
  }

  const token = await expectedToken();
  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, token!, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30, // 30 days
  });
  return res;
}
