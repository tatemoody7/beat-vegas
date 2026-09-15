import { prisma } from "@/lib/prisma";

// The real-money pause (docs/STOPPING_RULE.md). One row in `app_settings`, key
// `rule_paused`, written only by scripts/rule_pause.py. Read here per request by
// POST /api/picks for every real-money first-half pick.
//
// Fail closed, and be precise about what that means:
//   row value "true"            -> paused: real money refused (RULE PAUSED)
//   row value anything else,    -> not paused. The Python writer controls the
//   or no row                      value; an absent row is "never switched on".
//   table missing / read error  -> UNREADABLE: real money refused too (RULE STATE
//                                  UNREADABLE). A switch we cannot see is not a
//                                  switch that is off. The table lands with the
//                                  Python migration BEFORE this code ships, so a
//                                  missing table here is a fault, not schema lag.
// Paper picks never touch this read.

export const RULE_PAUSED_KEY = "rule_paused";

export type RulePause =
  | { paused: false }
  | { paused: true; note: string | null; since: Date | null }
  | { paused: "unreadable"; reason: string };

export const NOT_PAUSED: RulePause = { paused: false };

export type RulePauseRow = {
  value: string | null;
  note: string | null;
  /** to_char(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') — naive UTC, no zone. */
  updated_at: string | null;
};

export const isMissingTable = (e: unknown): boolean =>
  /relation .* does not exist|no such table/i.test(
    String((e as Error)?.message ?? e),
  );

/** Naive-UTC text from to_char → Date. Same idiom as lib/boardHealth.ts. */
export function utcFrom(s: string | null): Date | null {
  if (!s) return null;
  const d = new Date(`${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Pure: rows → state. Only the exact string "true" pauses. */
export function rulePauseFrom(rows: RulePauseRow[]): RulePause {
  const row = rows[0];
  if (!row) return NOT_PAUSED;
  if ((row.value ?? "").trim() !== "true") return NOT_PAUSED;
  return {
    paused: true,
    note: row.note && row.note.trim() ? row.note.trim() : null,
    since: utcFrom(row.updated_at),
  };
}

/** One primary-key lookup. Never throws: a failed read is the UNREADABLE state. */
export async function getRulePause(): Promise<RulePause> {
  try {
    const rows = await prisma.$queryRaw<RulePauseRow[]>`
      SELECT value, note,
             to_char(updated_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS updated_at
        FROM app_settings
       WHERE key = ${RULE_PAUSED_KEY}
       LIMIT 1`;
    return rulePauseFrom(rows);
  } catch (e) {
    const msg = String((e as Error)?.message ?? e);
    console.error("[rulePause] state unreadable:", msg);
    return {
      paused: "unreadable",
      reason: isMissingTable(e)
        ? "the app_settings table does not exist"
        : "could not read app_settings",
    };
  }
}
