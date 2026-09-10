import { NextResponse } from "next/server";
import { deletePick, updatePick } from "@/lib/picks";
import { parsePickEdit } from "@/lib/pickRules";

// PATCH /api/picks/<id> — correct a PENDING pick's price, stake, note or bonus
// flag. Entry mistakes are normal (a price typed from memory, a bonus bet that
// staked more than a flat unit); a graded pick is immutable, because a ledger
// that can be rewritten once the result is known proves nothing.
export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const pickId = Number(id);
  if (!Number.isFinite(pickId)) {
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
  const ok = await updatePick(pickId, parsed.edit);
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
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const pickId = Number(id);
  if (!Number.isFinite(pickId)) {
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  }
  const ok = await deletePick(pickId);
  if (!ok) {
    return NextResponse.json(
      { error: "pick not found or already graded (immutable)" },
      { status: 409 },
    );
  }
  return NextResponse.json({ ok: true });
}
