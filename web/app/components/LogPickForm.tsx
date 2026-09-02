"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { suggestedUnits } from "@/lib/kelly";
import type { PickReason, Verdict } from "@/lib/verdict";

// Everything the This Week card knows at the moment you decide, frozen onto the
// pick (docs/BETTING_POLICY.md "measuring, not promising"). The POST body field
// names are the contract shared with scripts/pick.py — keep them in step.
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
  /** Market no-vig fair-under at Hard Rock's number — feeds the advisory Kelly line. */
  fairUnder: number | null;
};

const REASON_TEXT: Record<PickReason, string> = {
  model_gap: "model gap at Hard Rock’s number",
  price_edge: "Hard Rock price edge only (no model read)",
  manual: "your own call",
};

// Real money is first-half unders at one flat unit; the stake is not a field.
// Paper picks are also one unit (so their record reads in units) but sit apart
// from the bankroll. WATCH defaults to paper — WATCH is not a bet (policy).
export default function LogPickForm({
  prefill,
  onDone,
}: {
  prefill: PickPrefill;
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
      setErr("Enter American odds (e.g. -110).");
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

  // Advisory only. Quarter-Kelly against the market's fair price says how big
  // the edge is; it is never a stake instruction (stakes are flat).
  const priceNum = Number(price);
  const kellyUnits =
    prefill.fairUnder !== null && Number.isFinite(priceNum)
      ? suggestedUnits(prefill.fairUnder, priceNum)
      : null;

  return (
    <form onSubmit={submit} className="bv-card p-4">
      <p className="mb-3 text-sm text-[var(--text)]">
        {`${prefill.away} @ ${prefill.home} — first-half under, `}
        <span className="font-mono font-semibold">1 unit</span>
        {` flat.`}
        <span className="ml-2 text-xs text-[var(--text-dim)]">
          {`Logged as ${prefill.verdict} · ${REASON_TEXT[prefill.reason]}`}
        </span>
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <label className={labelCls}>
          Your line (1H total, under)
          <input
            type="number"
            step={0.5}
            value={line}
            onChange={(e) => setLine(e.target.value)}
            className={field}
          />
        </label>
        <label
          className={labelCls}
          title="The odds you are taking (e.g. −110)."
        >
          Odds
          <input
            type="number"
            step={5}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className={field}
          />
        </label>
        <label
          className="flex items-center gap-2 self-end pb-2 text-xs text-[var(--text-muted)]"
          title="Track the pick with nothing at risk. Paper picks are graded like real ones but kept in their own record, so they never flatter your real numbers."
        >
          <input
            type="checkbox"
            checked={isPaper}
            onChange={(e) => setIsPaper(e.target.checked)}
          />
          Paper pick (no money on it)
          {isPaper && (
            <span className="bv-fac-badge bv-fac-badge-amber">PAPER</span>
          )}
        </label>

        <label className={`${labelCls} sm:col-span-3`}>
          Note (why you took it — for the Monday review)
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. both defenses elite, slow tempo, wind 18mph"
            className={field}
          />
        </label>
      </div>

      {kellyUnits !== null && (
        <p className="mt-3 text-xs text-[var(--text-dim)]">
          {kellyUnits > 0
            ? `Advisory only: against the market’s fair price (${(100 * (prefill.fairUnder ?? 0)).toFixed(1)}% under) quarter-Kelly would size this at ${kellyUnits.toFixed(1)} units. Every bet is still 1 flat unit.`
            : `Advisory only: at ${price} this under does not clear the market’s fair price (${(100 * (prefill.fairUnder ?? 0)).toFixed(1)}% under). Every bet is still 1 flat unit.`}
        </p>
      )}

      {err && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {err}
        </p>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button type="submit" disabled={busy} className="bv-btn">
          {busy ? "Logging…" : isPaper ? "Log paper pick" : "Log bet (1 unit)"}
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
