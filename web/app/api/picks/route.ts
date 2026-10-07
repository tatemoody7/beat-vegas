import { NextRequest, NextResponse } from "next/server";
import { createPick, DuplicatePickError } from "@/lib/picks";
import { parsePickBody } from "@/lib/pickRules";
import { requireAuth } from "@/lib/session";
import { evaluateRealTicket, evaluationMode } from "@/lib/ticketPolicy";

// POST /api/picks — log a REAL ticket on a current-slate game. Validation and
// the betting policy (1H-only real money, flat 1 unit, 5-bet weekly cap, the
// card's kill numbers) live in lib/pickRules.ts so they are unit-tested; the
// DB facts are gathered by lib/ticketPolicy.ts, shared with PATCH. Paper is
// written by the card build only (parsePickBody refuses it, 2026-10-07).
function dbError(where: string, e: unknown) {
  console.error(`[api/picks] ${where} failed:`, e);
  return NextResponse.json(
    { error: "could not reach the database — the pick was NOT logged" },
    { status: 503 },
  );
}

export async function POST(req: NextRequest) {
  // The site reads publicly; a WRITE needs the cookie. Checked here as well as
  // in middleware so a matcher edit can never open the ledger.
  const denied = await requireAuth(req);
  if (denied) return denied;
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const parsed = parsePickBody(body);
  if (!parsed.ok) {
    return NextResponse.json(
      { error: parsed.error },
      { status: parsed.status },
    );
  }
  const { pick } = parsed;
  const now = new Date();
  // A ticket written well before it is logged (2026-09-28) is judged by the
  // read in force THEN; lib/ticketPolicy.ts decides which read, one place for
  // this route and for PATCH /api/picks/<id>.
  const judgedBy = await evaluateRealTicket({
    pick,
    mode: evaluationMode(pick.betAt ?? null, now),
    now,
  });
  if (!judgedBy.ok) {
    return NextResponse.json(
      { error: judgedBy.error },
      { status: judgedBy.status },
    );
  }
  const judged = { ...pick, verdict: judgedBy.verdict };

  let tracked: boolean;
  try {
    ({ tracked } = await createPick(judged));
  } catch (e) {
    // The uq_manual_pick_per_ledger backstop fired. The duplicate check above
    // already passed, so this is the race it cannot close — a double-click, or
    // a retry of a request that had in fact succeeded. Either way the pick the
    // caller wanted is on file, so 409 (the same status the check itself
    // returns) is the honest answer, not a 500.
    if (e instanceof DuplicatePickError) {
      return NextResponse.json({ error: e.message }, { status: 409 });
    }
    return dbError("createPick", e);
  }
  return NextResponse.json(
    {
      ok: true,
      ...(tracked
        ? {}
        : {
            warning:
              "Pick saved, but the verdict snapshot was not stored — the tracking columns are missing (run the manual_picks migration).",
          }),
    },
    { status: 201 },
  );
}
