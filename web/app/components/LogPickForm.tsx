"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { usd } from "@/lib/format";
import { labelOf, REASON_TEXT, VERDICT_TEXT } from "@/lib/labels";
import type { PickReason, Verdict } from "@/lib/verdict";

// Everything the board knows at the moment you decide, frozen onto the pick
// (docs/BETTING_POLICY.md "measuring, not promising"). The POST body field
// names are the contract shared with scripts/pick.py — keep them in step.
//
// Stakes are flat, so the form has no size to advise on: the quarter-Kelly
// advisory line is gone (spec §19.12).
export type PickPrefill = {
  gameId: number;
  away: string;
  home: string;
  /** Default line: Hard Rock's first-half total, else the market's, else our estimate. */
  line: number | null;
  /** Hard Rock's under price when posted. */
  price: number | null;
  verdict: Verdict;
  reason: PickReason;
  /** Hard Rock's line minus our number (the gap that gated the verdict). */
  gap: number | null;
  ev: number | null;
  hrLine: number | null;
};

// Real money is first-half unders at one flat unit; the stake is not a field.
// Paper picks are also one unit (so their record reads in units) but sit apart
// from the bankroll. WATCH defaults to paper — WATCH is not a bet (policy).
export default function LogPickForm({
  prefill,
  unitUsd,
  onDone,
}: {
  prefill: PickPrefill;
  /** The flat stake. Passed in: lib/homeBoard reads the environment (and
   *  pulls in Prisma), which a client component must never import. */
  unitUsd: number;
  onDone?: () => void;
}) {
  const router = useRouter();
  const [line, setLine] = useState<string>(
    prefill.line === null ? "" : String(prefill.line),
  );
  const [price, setPrice] = useState<string>(String(prefill.price ?? -110));
  const [isPaper, setIsPaper] = useState(prefill.verdict !== "BET");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    const lineNum = Number(line);
    if (line.trim() === "" || !Number.isFinite(lineNum) || lineNum <= 0) {
      setErr("Enter the first-half total you are taking the under on.");
      return;
    }
    const priceNum = Number(price);
    if (!Number.isInteger(priceNum) || Math.abs(priceNum) < 100) {
      setErr("Enter the odds as a number, like -110.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/picks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gameId: prefill.gameId,
          market: "1H",
          line: lineNum,
          price: priceNum,
          isPaper,
          note: note.trim() || undefined,
          verdict: prefill.verdict,
          reason: prefill.reason,
          gap: prefill.gap,
          ev: prefill.ev,
          hrLine: prefill.hrLine,
        }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(j.error || `failed (${res.status})`);
      setNote("");
      onDone?.();
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const field = "bv-input";
  const labelCls =
    "flex flex-col gap-1 text-xs font-medium text-[var(--text-muted)]";
  const hintCls = "text-xs text-[var(--text-dim)]";
  const verdictWord = labelOf(VERDICT_TEXT, prefill.verdict, "Pass");

  return (
    <form onSubmit={submit} className="bv-card p-4">
      <p className="mb-3 text-sm text-[var(--text)]">
        {`${prefill.away} @ ${prefill.home} — first-half under, one unit.`}
        <span className="ml-2 text-xs text-[var(--text-dim)]">
          {`Logged as ${verdictWord} · ${REASON_TEXT[prefill.reason].long}`}
        </span>
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className={labelCls}>
          The first-half total you are taking under
          <input
            type="number"
            step={0.5}
            value={line}
            onChange={(e) => setLine(e.target.value)}
            className={field}
          />
        </label>
        <label className={labelCls}>
          Odds
          <input
            type="number"
            step={5}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className={field}
          />
          <span className={hintCls}>As a number, like -110.</span>
        </label>
        <div className="flex flex-col gap-1 self-end pb-2">
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <input
              type="checkbox"
              checked={isPaper}
              onChange={(e) => setIsPaper(e.target.checked)}
            />
            Paper pick — no money on it
          </label>
          <span className={hintCls}>
            Graded like a real bet, but kept in its own record.
          </span>
        </div>
        {!isPaper && prefill.verdict && prefill.verdict !== "BET" && (
          <p className="text-xs text-[var(--warn)] sm:col-span-3">
            {`This site rates the game ${verdictWord}, not Bet. Logging it as real money is fine — Results will show it separately so you can see how your own calls do.`}
          </p>
        )}

        <label className={`${labelCls} sm:col-span-3`}>
          Note — why you took it
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="both defenses good, slow pace, wind 18mph"
            className={field}
          />
        </label>
      </div>

      {err && (
        <p role="alert" className="mt-2 text-sm text-[var(--bad)]">
          {err}
        </p>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button type="submit" disabled={busy} className="bv-btn">
          {busy
            ? "Logging…"
            : isPaper
              ? "Log paper pick"
              : `Log bet (${usd(unitUsd)})`}
        </button>
        {onDone && (
          <button
            type="button"
            onClick={onDone}
            className="bv-nav-link text-xs"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
