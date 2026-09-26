import { signed } from "@/lib/format";
import {
  BLOCKER_SHORT,
  labelOf,
  REASON_TEXT,
  VERDICT_TEXT,
} from "@/lib/labels";
import { isOffPolicy } from "@/lib/pickRules";
import type { PickReason, Verdict } from "@/lib/verdict";

// The one sentence that says what the site thought at the moment a pick was
// logged: "Bet · model gap · +2.2 vs our number · real money on a Watch ·
// blocked by price". Shared by the Results picks table and the Track record
// ledger so the two can never phrase the frozen decision differently. Legacy
// picks (logged before the tracking columns) show a dash. Pure: no prisma, so
// a "use client" component may import it.
export type LoggedAsInput = {
  verdictAtPick: Verdict | null;
  reason: PickReason | null;
  gapAtPick: number | null;
  isPaper: boolean;
  blocker: string | null;
};

export function loggedAs(p: LoggedAsInput): string {
  if (!p.verdictAtPick && !p.reason) return "—";
  const parts: (string | null)[] = [
    p.verdictAtPick ? labelOf(VERDICT_TEXT, p.verdictAtPick, "Pass") : null,
    p.reason ? REASON_TEXT[p.reason].short : null,
  ];
  if (p.gapAtPick !== null) {
    parts.push(`${signed(p.gapAtPick, 1)} vs our number`);
  }
  if (isOffPolicy(p)) parts.push("real money on a Watch");
  if (p.isPaper && p.blocker && p.blocker !== "none") {
    parts.push(
      `blocked by ${labelOf(BLOCKER_SHORT, p.blocker, "an input").toLowerCase()}`,
    );
  }
  return parts.filter(Boolean).join(" · ");
}
