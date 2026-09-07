"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { BetSlip as Slip, BetSlipRow } from "@/lib/betSlip";
import { american } from "@/lib/format";

// The Saturday-morning bet slip: this week's BETs from the latest card, ranked
// by gap, each with Hard Rock's line + price and the kill numbers, and ONE tap
// to log the real ticket at the shown number ("I took this"). Tap the line or
// price to edit when Hard Rock's number differs at bet time. Server-side rules
// (lib/pickRules.ts: 1H only, flat unit, weekly cap, one real pick per game,
// no post-kickoff) are unchanged — this is only a faster front door to them.

function SlipRow({ r, disabled }: { r: BetSlipRow; disabled: boolean }) {
  const router = useRouter();
  const [line, setLine] = useState<string>(
    r.hrLine === null ? "" : String(r.hrLine),
  );
  const [price, setPrice] = useState<string>(String(r.hrPrice ?? -110));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function take() {
    setErr(null);
    const lineNum = Number(line);
    const priceNum = Number(price);
    if (line.trim() === "" || !Number.isFinite(lineNum) || lineNum <= 0) {
      setErr("Enter the first-half total you took the under on.");
      return;
    }
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
          gameId: r.gameId,
          market: "1H",
          line: lineNum,
          price: priceNum,
          isPaper: false,
          verdict: "BET",
          reason: "model_gap",
          gap: r.gap,
          ev: r.ev,
          hrLine: r.hrLine,
          note: `bet slip: took u${lineNum} ${priceNum > 0 ? "+" : ""}${priceNum} on Hard Rock`,
        }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(j.error || `failed (${res.status})`);
      setDone(true);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const status = done ? "logged" : r.status;
  const dim = status !== "open";

  return (
    <li className="border-t border-[var(--border-soft)] py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-xs text-[var(--text-dim)]">
          {r.capRank === null ? "—" : `#${r.capRank}`}
        </span>
        <span
          className={`font-semibold ${dim ? "text-[var(--text-muted)]" : "text-[var(--text)]"}`}
        >
          {r.matchup}
        </span>
        <span className="text-xs text-[var(--text-dim)]">
          {r.kick ?? "kickoff TBD"}
        </span>
        <span className="font-mono text-xs text-[var(--text-muted)]">
          {`1H UNDER ${r.line.replace(/^u/, "")} on Hard Rock`}
        </span>
        {r.kill !== "" && (
          <span
            className="font-mono text-xs text-[var(--text-dim)]"
            title="Do not bet below this number or at a worse price — the edge is gone."
          >
            {`kill: ${r.kill}`}
          </span>
        )}
        <span className="ml-auto flex items-center gap-2">
          {status === "logged" && (
            <span className="rounded-md border border-[var(--accent-strong)] px-1.5 text-xs text-[var(--accent)]">
              {r.loggedLine !== null
                ? `logged u${r.loggedLine}${r.loggedPrice !== null ? ` ${american(r.loggedPrice)}` : ""}`
                : "logged"}
            </span>
          )}
          {status === "over_cap" && (
            <span
              className="rounded-md border border-[var(--border)] px-1.5 text-xs text-[var(--text-dim)]"
              title="Every gate passed; beyond the weekly cap, so paper only."
            >
              over cap · paper only
            </span>
          )}
          {status === "kicked_off" && (
            <span className="text-xs text-[var(--text-dim)]">kicked off</span>
          )}
          {status === "open" && (
            <>
              <label className="flex items-center gap-1 text-xs text-[var(--text-dim)]">
                u
                <input
                  className="bv-input w-16 py-0.5 font-mono text-xs"
                  inputMode="decimal"
                  step="0.5"
                  value={line}
                  onChange={(e) => setLine(e.target.value)}
                  aria-label="first-half total taken"
                  disabled={busy || disabled}
                />
              </label>
              <label className="flex items-center gap-1 text-xs text-[var(--text-dim)]">
                at
                <input
                  className="bv-input w-16 py-0.5 font-mono text-xs"
                  inputMode="numeric"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  aria-label="price taken"
                  disabled={busy || disabled}
                />
              </label>
              <button
                type="button"
                onClick={take}
                disabled={busy || disabled}
                className="bv-btn text-xs"
                title={
                  disabled
                    ? "The weekly cap is used up."
                    : "Log this as a real-money first-half under at the number shown."
                }
              >
                {busy ? "Saving…" : "I took this"}
              </button>
            </>
          )}
        </span>
      </div>
      {err !== null && <p className="mt-1 text-xs text-[var(--over)]">{err}</p>}
    </li>
  );
}

export default function BetSlip({
  slip,
  week,
}: {
  slip: Slip;
  week: number | null;
}) {
  const capUsed = slip.used >= slip.cap;
  return (
    <section className="bv-card mb-4 p-4" aria-label="Bet slip">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          {week === null ? "Bet slip" : `Bet slip · Week ${week}`}
        </h2>
        <span
          className={`font-mono text-xs ${capUsed ? "text-[var(--accent)]" : "text-[var(--text-dim)]"}`}
          title="Real-money first-half bets logged this week against the weekly cap."
        >
          {`${slip.used} of ${slip.cap} used`}
        </span>
      </div>
      {slip.rows.length === 0 ? (
        <p className="mt-2 text-sm text-[var(--text-muted)]">
          No bets this week. Zero is a valid week — the cap is a ceiling, not a
          target.
        </p>
      ) : (
        <ul className="mt-2">
          {slip.rows.map((r) => (
            <SlipRow
              key={r.gameId}
              r={r}
              disabled={capUsed && r.status === "open"}
            />
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        Verify Hard Rock’s number before you tap. Edit the line or price if you
        got a different one; a bet below the kill line or at a worse price is
        not the same bet.
      </p>
    </section>
  );
}
