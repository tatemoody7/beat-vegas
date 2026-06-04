"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { PickFull } from "@/lib/picks";

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
        No logged picks yet.
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
            <th>Your line</th>
            <th title="The under score and our number at the time you logged the pick.">Model @ pick</th>
            <th>Result</th>
            <th title="Profit in units. 1 unit = one standard bet.">Units</th>
            <th title="Line value (CLV): positive = the line moved your way after you'd bet.">Line value</th>
            <th>Note</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <tr key={p.id} className="align-top">
              <td className="text-[var(--text-muted)]">{p.week ?? "—"}</td>
              <td className="text-[var(--text)]">
                {p.away} <span className="text-[var(--text-dim)]">@</span> {p.home}
              </td>
              <td className="text-[var(--text-muted)]">
                {p.line !== null ? `under ${p.line}` : "—"}
              </td>
              <td className="text-[var(--text-muted)]">
                {p.modelScore !== null ? `${p.modelScore}` : "—"}
                {p.modelLine !== null ? ` @ ${p.modelLine}` : ""}
              </td>
              <td>
                <span
                  style={{
                    color:
                      p.result === "under"
                        ? "#16a34a"
                        : p.result === "over"
                          ? "#dc2626"
                          : "#9ca3af",
                  }}
                >
                  {p.result}
                </span>
              </td>
              <td
                className="font-mono"
                style={{
                  color:
                    p.units === null ? "#9ca3af" : p.units >= 0 ? "#16a34a" : "#dc2626",
                }}
              >
                {num(p.units)}
              </td>
              <td className="font-mono text-[var(--text-muted)]">{num(p.clv)}</td>
              <td className="max-w-xs text-[var(--text-dim)]">{p.note ?? "—"}</td>
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
