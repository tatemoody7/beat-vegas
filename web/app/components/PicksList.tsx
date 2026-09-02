"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { PickFull } from "@/lib/picks";
import type { PickReason } from "@/lib/verdict";

const REASON_SHORT: Record<PickReason, string> = {
  model_gap: "model gap",
  price_edge: "price edge",
  manual: "your call",
};

// "BET · model gap · HR gap +2.2" — the decision frozen at log time; legacy
// picks (before the tracking columns) show a dash.
function loggedAs(p: PickFull): string {
  if (!p.verdictAtPick && !p.reason) return "—";
  const parts = [p.verdictAtPick, p.reason ? REASON_SHORT[p.reason] : null];
  if (p.gapAtPick !== null) {
    parts.push(`HR gap ${p.gapAtPick > 0 ? "+" : ""}${p.gapAtPick.toFixed(1)}`);
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
        No picks logged for this selection. Log bets from the This Week cards.
      </p>
    );
  }

  const num = (n: number | null, dp = 2) =>
    n === null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;

  return (
    <div className="bv-table-wrap">
      <table className="bv-table">
        <thead>
          <tr>
            <th>Wk</th>
            <th>Matchup</th>
            <th>Market</th>
            <th>Your line</th>
            <th title="The under score and our number at the time you logged the pick.">
              Model @ pick
            </th>
            <th title="The This Week verdict, the reason, and Hard Rock’s gap vs our number when you logged it.">
              Logged as
            </th>
            <th>Result</th>
            <th title="Profit in units. 1 unit = one standard bet.">Units</th>
            <th title="Line value (CLV): positive = the line moved your way after you'd bet.">
              Line value
            </th>
            <th>Note</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <tr key={p.id} className="align-top">
              <td className="text-[var(--text-muted)]">{p.week ?? "—"}</td>
              <td className="text-[var(--text)]">
                {p.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                {p.home}
              </td>
              <td className="text-[var(--text-muted)]">
                {p.market === "full" ? "Full game" : "1H"}
                {p.isPaper && (
                  <span
                    className="bv-fac-badge bv-fac-badge-amber ml-1"
                    title="Paper pick — nothing at risk; kept out of your real record."
                  >
                    PAPER
                  </span>
                )}
              </td>
              <td className="text-[var(--text-muted)]">
                {p.line !== null ? `under ${p.line}` : "—"}
              </td>
              <td className="text-[var(--text-muted)]">
                {p.modelScore !== null ? `${p.modelScore}` : "—"}
                {p.modelLine !== null ? ` @ ${p.modelLine}` : ""}
              </td>
              <td className="text-xs text-[var(--text-muted)]">
                {loggedAs(p)}
              </td>
              <td>
                <span
                  style={{
                    color:
                      p.result === "under"
                        ? "var(--under-strong)"
                        : p.result === "over"
                          ? "var(--over)"
                          : "var(--text-dim)",
                  }}
                >
                  {p.result}
                </span>
              </td>
              <td
                className="font-mono"
                style={{
                  color:
                    p.units === null
                      ? "var(--text-dim)"
                      : p.units >= 0
                        ? "var(--under-strong)"
                        : "var(--over)",
                }}
              >
                {num(p.units)}
              </td>
              <td className="font-mono text-[var(--text-muted)]">
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
                    className="text-xs text-[var(--text-dim)] hover:text-red-400 disabled:opacity-50"
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
  );
}
