import { NextResponse } from "next/server";
import { deletePick } from "@/lib/picks";

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
