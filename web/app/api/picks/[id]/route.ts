import { NextRequest, NextResponse } from "next/server";
import { deletePick, getEditablePick, updatePick } from "@/lib/picks";
import { DEFAULT_STAKE, parsePickEdit } from "@/lib/pickRules";
import { requireAuth } from "@/lib/session";
import { evaluateRealTicket, evaluationMode } from "@/lib/ticketPolicy";

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

// Paper is the build's (2026-10-07): the card writes one paper pick per
// qualifying game at the build's line and price, and that row IS the stopping
// rule's observation. Editing or deleting it would change what H-STOP-2 reads.
const PAPER_FROZEN = () =>
  NextResponse.json(
    {
      error:
        "PAPER IS FROZEN — paper picks are written by the card build and are the stopping rule's record; they cannot be edited or deleted.",
    },
    { status: 409 },
  );
const NOT_FOUND = () =>
  NextResponse.json({ error: "pick not found" }, { status: 404 });

// PATCH /api/picks/<id> — correct a REAL ticket's price, stake or note before
// kickoff. Entry mistakes are normal (a price typed from memory, a bonus bet
// that staked more than a flat unit); nothing is editable from kickoff, because
// a ledger that can be rewritten once the result is known proves nothing.
//
// A changed PRICE is re-judged (2026-10-07) by the same evaluator a new ticket
// goes through (lib/ticketPolicy.ts), at the time the ticket was written and
// against the verdict frozen on it: a ticket logged at a passing price could
// otherwise be edited to one the kill price refuses. The bonus flag is not
// editable and a price cannot be cleared (parsePickEdit).
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
  let row: Awaited<ReturnType<typeof getEditablePick>>;
  try {
    row = await getEditablePick(pickId);
  } catch (e) {
    return serverError("getEditablePick", e);
  }
  if (!row) return NOT_FOUND();
  if (row.isPaper) return PAPER_FROZEN();

  const edit = parsed.edit;
  if (edit.price !== undefined && edit.price !== row.price) {
    if (row.gameId === null) {
      return NextResponse.json(
        {
          error:
            "This ticket is not matched to a game, so a new price cannot be checked against the card. Leave the price as it is.",
        },
        { status: 409 },
      );
    }
    const now = new Date();
    const judged = await evaluateRealTicket({
      pick: {
        gameId: row.gameId,
        market: row.market,
        line: row.line,
        stake: DEFAULT_STAKE,
        price: edit.price,
        isPaper: false,
        isBonus: row.isBonus,
        betAt: row.writtenAt,
      },
      mode: evaluationMode(row.writtenAt, now),
      now,
      excludePickId: row.id,
      frozenVerdict: row.verdictAtPick,
    });
    if (!judged.ok) {
      return NextResponse.json(
        { error: judged.error },
        { status: judged.status },
      );
    }
  }

  let ok: boolean;
  try {
    ok = await updatePick(pickId, edit);
  } catch (e) {
    return serverError("updatePick", e);
  }
  if (!ok) {
    return NextResponse.json(
      {
        error:
          "already graded, or its game has kicked off — the ledger is frozen from kickoff",
      },
      { status: 409 },
    );
  }
  return NextResponse.json({ ok: true });
}

// DELETE /api/picks/<id> — remove a REAL ticket before kickoff only.
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
    const row = await getEditablePick(pickId);
    if (!row) return NOT_FOUND();
    if (row.isPaper) return PAPER_FROZEN();
    ok = await deletePick(pickId);
  } catch (e) {
    return serverError("deletePick", e);
  }
  if (!ok) {
    return NextResponse.json(
      {
        error:
          "already graded, or its game has kicked off — the ledger is frozen from kickoff",
      },
      { status: 409 },
    );
  }
  return NextResponse.json({ ok: true });
}
