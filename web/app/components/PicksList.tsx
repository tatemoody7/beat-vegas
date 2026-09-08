"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  BLOCKER_SHORT,
  labelOf,
  REASON_TEXT,
  RESULT_PENDING,
  RESULT_TEXT,
} from "@/lib/labels";
import type { PickFull } from "@/lib/picks";
import { isOffPolicy } from "@/lib/picks";

// The word frozen onto the pick. "EDGE" is legacy for the amber tier and reads
// "Watch" like everywhere else on screen.
const VERDICT_WORD: Record<string, string> = {
  BET: "Bet",
  WATCH: "Watch",
  EDGE: "Watch",
  PASS: "Pass",
};

// Outcome colours (never cyan): won green, lost red, push grey.
const RESULT_COLOR: Record<string, string> = {
  under: "var(--good)",
  over: "var(--bad)",
  push: "var(--push)",
};

// Every logged pick, with the decision frozen at log time. Nothing here is
// explained in a `title=` tooltip (a phone never shows one) — the caption under
// the table carries it, and every enum goes through lib/labels.

// "Bet · model gap · +2.2 vs our number · real money on a Watch · blocked by
// price". Legacy picks (logged before the tracking columns) show a dash.
function loggedAs(p: PickFull): string {
  if (!p.verdictAtPick && !p.reason) return "—";
  const parts: (string | null)[] = [
    p.verdictAtPick
      ? labelOf(VERDICT_WORD, p.verdictAtPick, p.verdictAtPick)
      : null,
    p.reason ? REASON_TEXT[p.reason].short : null,
  ];
  if (p.gapAtPick !== null) {
    parts.push(
      `${p.gapAtPick > 0 ? "+" : ""}${p.gapAtPick.toFixed(1)} vs our number`,
    );
  }
  if (isOffPolicy(p)) parts.push("real money on a Watch");
  if (p.isPaper && p.blocker && p.blocker !== "none") {
    parts.push(
      `blocked by ${labelOf(BLOCKER_SHORT, p.blocker, "an input").toLowerCase()}`,
    );
  }
  return parts.filter(Boolean).join(" · ");
}

export default function PicksList({ picks }: { picks: PickFull[] }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState<number | null>(null);

  async function del(id: number) {
    setDeleting(id);
    try {
      const res = await fetch(`/api/picks/${id}`, { method: "DELETE" });
      if (res.ok) router.refresh();
    } finally {
      setDeleting(null);
    }
  }

  if (picks.length === 0) {
    return (
      <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
        No picks here. Log bets from the board.
      </p>
    );
  }

  const num = (n: number | null, dp = 2) =>
    n === null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;

  return (
    <>
      <div className="bv-table-wrap">
        <table className="bv-table">
          <thead>
            <tr>
              <th className="bv-num">Week</th>
              <th>Matchup</th>
              <th>Market</th>
              <th className="bv-num">Your line</th>
              <th className="bv-num">Our number then</th>
              <th>Why you logged it</th>
              <th>Result</th>
              <th className="bv-num">Units</th>
              <th className="bv-num">Line value</th>
              <th>Note</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {picks.map((p) => (
              <tr key={p.id} className="align-top">
                <td className="bv-num text-[var(--text-muted)]">
                  {p.week ?? "—"}
                </td>
                <td className="text-[var(--text)]">
                  {p.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                  {p.home}
                </td>
                <td className="text-[var(--text-muted)]">
                  {p.market === "full" ? "Full game" : "First half"}
                  {p.isPaper && (
                    <span className="bv-badge bv-badge--warn ml-1">
                      paper — no money on it
                    </span>
                  )}
                </td>
                <td className="bv-num text-[var(--text-muted)]">
                  {p.line !== null ? `under ${p.line}` : "—"}
                </td>
                <td className="bv-num text-[var(--text-muted)]">
                  {p.modelLine ?? "—"}
                </td>
                <td className="text-xs text-[var(--text-muted)]">
                  {loggedAs(p)}
                </td>
                <td>
                  <span
                    style={{
                      color: p.graded
                        ? labelOf(RESULT_COLOR, p.result, "var(--text-dim)")
                        : "var(--text-dim)",
                    }}
                  >
                    {p.graded
                      ? labelOf(RESULT_TEXT, p.result, RESULT_PENDING)
                      : RESULT_PENDING}
                  </span>
                </td>
                <td
                  className="bv-num font-mono"
                  style={{
                    color:
                      p.units === null
                        ? "var(--text-dim)"
                        : p.units >= 0
                          ? "var(--good)"
                          : "var(--bad)",
                  }}
                >
                  {num(p.units)}
                </td>
                <td className="bv-num font-mono text-[var(--text-muted)]">
                  {num(p.clv)}
                </td>
                <td className="max-w-xs text-[var(--text-dim)]">
                  {p.note ?? "—"}
                </td>
                <td>
                  {!p.graded && (
                    <button
                      onClick={() => del(p.id)}
                      disabled={deleting === p.id}
                      className="text-xs text-[var(--text-dim)] hover:text-[var(--bad)] disabled:opacity-50"
                    >
                      {deleting === p.id ? "…" : "delete"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
        “Our number then” and “Why you logged it” are frozen at the moment you
        logged the pick. Line value positive means the line moved your way
        afterwards.
      </p>
    </>
  );
}
