import { NextRequest, NextResponse } from "next/server";
import { deletePick, updatePick } from "@/lib/picks";
import { parsePickEdit } from "@/lib/pickRules";
import { requireAuth } from "@/lib/session";

// A pick id is a row id: 1.5 and -3 are not ids. Number.isFinite accepted
// both; they matched nothing and fell through as a 409 "not found", which
// is the wrong answer to a malformed request.
const badId = (n: number) => !Number.isInteger(n) || n <= 0;

// The DB is the one thing here that can fail in a way the caller did not
// cause. Without this the route returned a bare framework 500 with no JSON
// body and the UI showed "failed (500)".
function serverError(where: string, e: unknown) {
  console.error(`[api/picks/:id] ${where} failed:`, e);
  return NextResponse.json(
    { error: "could not reach the database — try again" },
    { status: 503 },
  );
}

// PATCH /api/picks/<id> — correct a PENDING pick's price, stake, note or bonus
// flag. Entry mistakes are normal (a price typed from memory, a bonus bet that
// staked more than a flat unit); a graded pick is immutable, because a ledger
// that can be rewritten once the result is known proves nothing.
export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const denied = await requireAuth(req);
  if (denied) return denied;
  const { id } = await params;
  const pickId = Number(id);
  if (badId(pickId)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const parsed = parsePickEdit(body);
  if (!parsed.ok) {
    return NextResponse.json(
      { error: parsed.error },
      { status: parsed.status },
    );
  }
  let ok: boolean;
  try {
    ok = await updatePick(pickId, parsed.edit);
  } catch (e) {
    return serverError("updatePick", e);
  }
  if (!ok) {
    return NextResponse.json(
      { error: "pick not found or already graded (immutable)" },
      { status: 409 },
    );
  }
  return NextResponse.json({ ok: true });
}

// DELETE /api/picks/<id> — remove a pending (ungraded) pick only.
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const denied = await requireAuth(req);
  if (denied) return denied;
  const { id } = await params;
  const pickId = Number(id);
  if (badId(pickId)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  let ok: boolean;
  try {
    ok = await deletePick(pickId);
  } catch (e) {
    return serverError("deletePick", e);
  }
  if (!ok) {
    return NextResponse.json(
      { error: "pick not found or already graded (immutable)" },
      { status: 409 },
    );
  }
  return NextResponse.json({ ok: true });
}
