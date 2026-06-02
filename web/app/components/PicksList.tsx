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
      <p className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
        No logged picks yet.
      </p>
    );
  }

  const num = (n: number | null, dp = 2) =>
    n === null ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(dp)}`;

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-800">
      <table className="w-full text-sm">
        <thead className="bg-gray-900 text-left text-gray-400">
          <tr>
            <th className="px-3 py-2 font-medium">Wk</th>
            <th className="px-3 py-2 font-medium">Matchup</th>
            <th className="px-3 py-2 font-medium">Your line</th>
            <th className="px-3 py-2 font-medium">Model @ pick</th>
            <th className="px-3 py-2 font-medium">Result</th>
            <th className="px-3 py-2 font-medium">Units</th>
            <th className="px-3 py-2 font-medium">CLV</th>
            <th className="px-3 py-2 font-medium">Note</th>
            <th className="px-3 py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {picks.map((p) => (
            <tr key={p.id} className="border-t border-gray-800 align-top">
              <td className="px-3 py-1.5 text-gray-400">{p.week ?? "—"}</td>
              <td className="px-3 py-1.5 text-gray-200">
                {p.away} <span className="text-gray-600">@</span> {p.home}
              </td>
              <td className="px-3 py-1.5 text-gray-300">
                {p.line !== null ? `u${p.line}` : "—"}
              </td>
              <td className="px-3 py-1.5 text-gray-400">
                {p.modelScore !== null ? `${p.modelScore}` : "—"}
                {p.modelLine !== null ? ` @ ${p.modelLine}` : ""}
              </td>
              <td className="px-3 py-1.5">
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
                className="px-3 py-1.5"
                style={{
                  color:
                    p.units === null ? "#9ca3af" : p.units >= 0 ? "#16a34a" : "#dc2626",
                }}
              >
                {num(p.units)}
              </td>
              <td className="px-3 py-1.5 text-gray-400">{num(p.clv)}</td>
              <td className="max-w-xs px-3 py-1.5 text-gray-500">{p.note ?? "—"}</td>
              <td className="px-3 py-1.5">
                {!p.graded && (
                  <button
                    onClick={() => del(p.id)}
                    disabled={deleting === p.id}
                    className="text-xs text-gray-500 hover:text-red-400 disabled:opacity-50"
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
