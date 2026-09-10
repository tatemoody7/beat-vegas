"use client";

import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { american, signed } from "@/lib/format";
import {
  BLOCKER_SHORT,
  labelOf,
  MARKET_TEXT,
  REASON_TEXT,
  RESULT_COLOR,
  RESULT_PENDING,
  RESULT_TEXT,
  VERDICT_TEXT,
} from "@/lib/labels";
import type { PickFull } from "@/lib/picks";
import { isOffPolicy } from "@/lib/picks";
import { EmptyLine } from "@/app/components/Section";

// Every logged pick, with the decision frozen at log time. Nothing here is
// explained in a `title=` tooltip (a phone never shows one) — the caption under
// the table carries it, and every enum goes through lib/labels.

// "Bet · model gap · +2.2 vs our number · real money on a Watch · blocked by
// price". Legacy picks (logged before the tracking columns) show a dash.
function loggedAs(p: PickFull): string {
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

export default function PicksList({ picks }: { picks: PickFull[] }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  // Independent of `editing` on purpose: reading the frozen note while you
  // correct it is useful, and a "one at a time" rule would make the two
  // states have to know about each other.
  const [open, setOpen] = useState<number | null>(null);
  const [draft, setDraft] = useState<{
    price: string;
    stake: string;
    isBonus: boolean;
    note: string;
  }>({ price: "", stake: "", isBonus: false, note: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function startEdit(p: PickFull) {
    setError(null);
    setEditing(p.id);
    setDraft({
      price: p.price === null ? "" : String(p.price),
      stake: p.stake === null ? "" : String(p.stake),
      isBonus: p.isBonus,
      note: p.note ?? "",
    });
  }

  async function save(id: number) {
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        price: draft.price.trim() === "" ? null : Number(draft.price),
        stake: Number(draft.stake),
        isBonus: draft.isBonus,
        note: draft.note.trim() === "" ? null : draft.note,
      };
      const res = await fetch(`/api/picks/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setEditing(null);
        router.refresh();
      } else {
        const j = await res.json().catch(() => ({}));
        setError(j.error ?? "Could not save that.");
      }
    } finally {
      setSaving(false);
    }
  }

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
    return <EmptyLine>No picks here. Log bets from the board.</EmptyLine>;
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
              <th className="bv-num">Price</th>
              <th className="bv-num">Stake</th>
              <th>Result</th>
              <th className="bv-num">Units</th>
              <th className="bv-num">Line value</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {picks.map((p) => (
              <React.Fragment key={p.id}>
                <tr className="align-top">
                  <td className="bv-num text-[var(--text-muted)]">
                    {p.week ?? "—"}
                  </td>
                  <td className="text-[var(--text)]">
                    {p.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                    {p.home}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {labelOf(MARKET_TEXT, p.market, "First half")}
                    {p.isPaper && (
                      <span className="bv-badge bv-badge--warn ml-1">
                        paper — no money on it
                      </span>
                    )}
                    {p.isBonus && (
                      <span className="bv-badge ml-1">
                        bonus — a loss costs nothing
                      </span>
                    )}
                  </td>
                  <td className="bv-num text-[var(--text-muted)]">
                    {p.line !== null ? `under ${p.line}` : "—"}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {p.price === null ? "—" : american(p.price)}
                  </td>
                  <td className="bv-num font-mono text-[var(--text-muted)]">
                    {p.stake === null ? "—" : `${p.stake}u`}
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
                  <td className="whitespace-nowrap">
                    <button
                      onClick={() => setOpen(open === p.id ? null : p.id)}
                      aria-expanded={open === p.id}
                      aria-controls={`pick-detail-${p.id}`}
                      className="text-xs text-[var(--text-dim)] hover:text-[var(--accent)]"
                    >
                      {open === p.id ? "hide" : "details"}
                    </button>
                    {!p.graded && (
                      <>
                        <button
                          onClick={() => startEdit(p)}
                          className="ml-2 text-xs text-[var(--text-dim)] hover:text-[var(--accent)]"
                        >
                          edit
                        </button>
                        <button
                          onClick={() => del(p.id)}
                          disabled={deleting === p.id}
                          className="ml-2 text-xs text-[var(--text-dim)] hover:text-[var(--bad)] disabled:opacity-50"
                        >
                          {deleting === p.id ? "…" : "delete"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
                {open === p.id && (
                  <tr id={`pick-detail-${p.id}`}>
                    <td
                      colSpan={10}
                      className="bg-[var(--surface-2)] px-3 py-3"
                    >
                      <dl className="grid grid-cols-1 gap-x-8 gap-y-2 text-xs sm:grid-cols-[auto_1fr]">
                        <dt className="text-[var(--text-dim)]">
                          Our number then
                        </dt>
                        <dd className="font-mono text-[var(--text-muted)]">
                          {p.modelLine ?? "—"}
                        </dd>
                        <dt className="text-[var(--text-dim)]">
                          Why you logged it
                        </dt>
                        <dd className="text-[var(--text-muted)]">
                          {loggedAs(p)}
                        </dd>
                        <dt className="text-[var(--text-dim)]">Note</dt>
                        <dd className="text-[var(--text-muted)]">
                          {p.note ?? "—"}
                        </dd>
                      </dl>
                      <p className="mt-2 text-xs leading-relaxed text-[var(--text-dim)]">
                        Both are frozen at the moment you logged the pick, so
                        they cannot be rewritten later.
                      </p>
                    </td>
                  </tr>
                )}
                {editing === p.id && (
                  <tr>
                    <td
                      colSpan={10}
                      className="bg-[var(--surface-2)] px-3 py-3"
                    >
                      <div className="flex flex-wrap items-end gap-3 text-xs">
                        <label className="flex flex-col gap-1">
                          <span className="text-[var(--text-dim)]">
                            Price (American)
                          </span>
                          <input
                            value={draft.price}
                            onChange={(e) =>
                              setDraft({ ...draft, price: e.target.value })
                            }
                            placeholder="-125"
                            className="w-24 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono"
                          />
                        </label>
                        <label className="flex flex-col gap-1">
                          <span className="text-[var(--text-dim)]">
                            Stake (units)
                          </span>
                          <input
                            value={draft.stake}
                            onChange={(e) =>
                              setDraft({ ...draft, stake: e.target.value })
                            }
                            placeholder="1"
                            className="w-24 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono"
                          />
                        </label>
                        <label className="flex items-center gap-2 pb-1">
                          <input
                            type="checkbox"
                            checked={draft.isBonus}
                            onChange={(e) =>
                              setDraft({ ...draft, isBonus: e.target.checked })
                            }
                          />
                          <span>Bonus bet (a loss books nothing)</span>
                        </label>
                        <label className="flex min-w-[16rem] flex-1 flex-col gap-1">
                          <span className="text-[var(--text-dim)]">Note</span>
                          <input
                            value={draft.note}
                            onChange={(e) =>
                              setDraft({ ...draft, note: e.target.value })
                            }
                            className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1"
                          />
                        </label>
                        <button
                          onClick={() => save(p.id)}
                          disabled={saving}
                          className="bv-btn disabled:opacity-50"
                        >
                          {saving ? "Saving…" : "Save"}
                        </button>
                        <button
                          onClick={() => setEditing(null)}
                          className="text-[var(--text-dim)] hover:text-[var(--text)]"
                        >
                          Cancel
                        </button>
                      </div>
                      {error && (
                        <p className="mt-2 text-xs text-[var(--bad)]">
                          {error}
                        </p>
                      )}
                      <p className="mt-2 text-xs text-[var(--text-dim)]">
                        {`One unit is $10. A bonus bet pays profit only, so a $20 bonus at -125 wins $16 and loses nothing — tick the box and set the stake to 2. Editing stops once the game is graded.`}
                      </p>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-[var(--text-dim)]">
        Line value positive means the line moved your way after the bet. Open a
        row for our number at the time, why it was logged, and the note.
      </p>
    </>
  );
}
