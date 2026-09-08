"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  blockReason,
  effectiveBlock,
  HARD_ROCK_URL,
  type BetSlip as Slip,
  type BetSlipRow,
} from "@/lib/betSlip";
import { lineLabel } from "@/lib/card";
import { american, fmt } from "@/lib/format";

// The Saturday-morning bet slip, used on a phone: this week's BETs from the
// latest card, ranked by gap, each reconciled against Hard Rock's LIVE line
// the same render loaded. Every row shows the card's number next to the live
// one, flags a move, and blocks the tap when the live number sits past the
// card's kill numbers (or the cap is used, or a card input was degraded). A
// bet takes two taps — arm, then confirm — and logs the entered line/price as
// the real ticket. Server-side rules (lib/pickRules.ts) still apply; this is
// only a faster front door to them. Amber = warning; green/red never appear.

const ARM_MS = 8_000;
/** Kickoff this close turns the clock amber. */
const SOON_MINUTES = 60;

const FAIR_TITLE = {
  exchange:
    "Kill numbers come off the card’s fair price from a no-vig exchange.",
  books:
    "Kill numbers come off the card’s fair price from the books’ consensus.",
  none: "Do not bet below this number or at a worse price — the edge is gone.",
} as const;

const usd = (n: number) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });

/** Entered text -> number for the kill check; null when blank/unparseable. */
const numOrNull = (s: string): number | null => {
  if (s.trim() === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

function SlipRow({ r, unitUsd }: { r: BetSlipRow; unitUsd: number }) {
  const router = useRouter();
  const [line, setLine] = useState<string>(
    r.liveLine === null ? "" : String(r.liveLine),
  );
  const [price, setPrice] = useState<string>(String(r.livePrice ?? -110));
  const [busy, setBusy] = useState(false);
  const [armed, setArmed] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disarm = () => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    setArmed(false);
  };
  useEffect(() => () => disarm(), []);

  const lineNum = numOrNull(line);
  const priceNum = numOrNull(price);
  // degraded/cap are hard blocks off the card; a kill block is re-checked
  // against what's actually entered (defaults to the live number) so raising
  // the entered line/price above the kill numbers clears it, matching what
  // the server (lib/pickRules.ts) judges on submit — the slip must never be
  // stricter than the rule it fronts.
  const { block, isLive: blockIsLive } = effectiveBlock(r, lineNum, priceNum);
  const disabled = busy || block !== null;

  const status = done ? "logged" : r.status;
  const open = status === "open";
  const soon =
    r.kickMinutes !== null && r.kickMinutes > 0 && r.kickMinutes < SOON_MINUTES;
  const stake = usd(unitUsd);
  const confirmLabel = `Confirm u${line} ${priceNum === null ? price : american(priceNum)} · ${stake}`;

  function edit(set: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLInputElement>) => {
      disarm();
      set(e.target.value);
    };
  }

  function arm() {
    setErr(null);
    setArmed(true);
    timer.current = setTimeout(() => setArmed(false), ARM_MS);
  }

  async function take() {
    disarm();
    setErr(null);
    if (lineNum === null || lineNum <= 0) {
      setErr("Enter the first-half total you took the under on.");
      return;
    }
    if (
      priceNum === null ||
      !Number.isInteger(priceNum) ||
      Math.abs(priceNum) < 100
    ) {
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
          reason: r.reason,
          gap: r.gap,
          ev: r.ev,
          hrLine: r.liveLine ?? r.hrLine,
          note: `bet slip: took u${fmt(lineNum)} ${american(priceNum)} on Hard Rock (card ${r.line})`,
        }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(j.error || `failed (${res.status})`);
      if (typeof j.warning === "string") setWarning(j.warning);
      setDone(true);
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  const liveLabel = lineLabel({ hrLine: r.liveLine, hrPrice: r.livePrice });

  return (
    <li className="border-t border-[var(--border-soft)] py-3 text-sm">
      {/* 1 — who, when */}
      <div className="flex flex-wrap items-baseline gap-x-2 text-xs text-[var(--text-dim)]">
        <span className="font-mono">
          {r.capRank === null ? "—" : `#${r.capRank}`}
        </span>
        <span className="text-[var(--text-dim)]">·</span>
        <span
          className={`text-sm font-semibold ${open ? "text-[var(--text)]" : "text-[var(--text-muted)]"}`}
        >
          {r.matchup}
        </span>
        {r.kicksIn !== null && (
          <>
            <span>·</span>
            <span className={soon ? "text-[var(--warn)]" : ""}>
              {r.kicksIn}
            </span>
          </>
        )}
        {r.kick !== null && <span>{`(${r.kick})`}</span>}
      </div>

      {/* 2 — card vs live */}
      <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs text-[var(--text-muted)]">
        {/* Each price group (line + price) stays on one line; a break can
            only land at the arrow between them, never mid-value. */}
        <span className="whitespace-nowrap">{`card ${r.line}`}</span>
        <span>→</span>
        <span className="whitespace-nowrap">{`live ${liveLabel}`}</span>
        {r.moved && (
          <span
            className="rounded-md border border-[var(--warn-border)] bg-[var(--warn-bg)] px-1.5 text-[var(--warn)]"
            title="Hard Rock’s line has moved off the card’s number."
          >
            moved
          </span>
        )}
        {/* Below 0.05 the gap is noise, not signal — mirrors the Python
            why-sentence threshold in beatvegas/card.py (abs(...) >= 0.05)
            that suppresses the same comparison there. One-line guard, kept
            inline since hrVsMarket has no other pure helper in lib/betSlip.ts. */}
        {r.hrVsMarket !== null && Math.abs(r.hrVsMarket) >= 0.05 && (
          <span
            className="text-[var(--text-dim)]"
            title="Hard Rock’s first-half line minus the market’s. Higher is better for an under."
          >
            {`HR ${r.hrVsMarket > 0 ? "+" : ""}${fmt(r.hrVsMarket)} vs market`}
          </span>
        )}
      </div>

      {/* 3 — kill numbers */}
      {r.kill !== "" && (
        <p
          className="mt-0.5 font-mono text-xs text-[var(--text-dim)]"
          title={FAIR_TITLE[r.fairSource ?? "none"]}
        >
          {`kill: ${r.kill}`}
        </p>
      )}

      {/* status / controls */}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {status === "logged" && (
          <span className="rounded-md border border-[var(--accent-strong)] px-1.5 py-0.5 text-xs text-[var(--accent)]">
            {r.loggedLine !== null
              ? `logged u${fmt(r.loggedLine)}${r.loggedPrice !== null ? ` ${american(r.loggedPrice)}` : ""}`
              : "logged"}
          </span>
        )}
        {status === "over_cap" && (
          <span
            className="rounded-md border border-[var(--border)] px-1.5 py-0.5 text-xs text-[var(--text-dim)]"
            title="Every gate passed; beyond the weekly cap, so paper only."
          >
            over cap · paper only
          </span>
        )}
        {status === "kicked_off" && (
          <span className="text-xs text-[var(--text-dim)]">kicked off</span>
        )}
        {open && (
          <>
            <label className="flex items-center gap-1 text-sm text-[var(--text-dim)]">
              u
              <input
                className="bv-input min-h-11 w-20 font-mono text-base"
                inputMode="decimal"
                step="0.5"
                value={line}
                onChange={edit(setLine)}
                aria-label="first-half total taken"
                disabled={busy}
              />
            </label>
            <label className="flex items-center gap-1 text-sm text-[var(--text-dim)]">
              at
              <input
                className="bv-input min-h-11 w-20 font-mono text-base"
                inputMode="numeric"
                value={price}
                onChange={edit(setPrice)}
                aria-label="price taken"
                disabled={busy}
              />
            </label>
            <span
              className="font-mono text-sm text-[var(--text-muted)]"
              title="Flat stake: one unit, every bet."
            >
              {stake}
            </span>
            <a
              href={HARD_ROCK_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center text-sm text-[var(--accent)] hover:underline"
            >
              Open Hard Rock ↗
            </a>
            <button
              type="button"
              onClick={armed ? take : arm}
              disabled={disabled}
              className="bv-btn min-h-11 text-sm"
              title={
                block !== null
                  ? blockReason(block, blockIsLive)
                  : armed
                    ? "Tap again to log this as a real-money first-half under at the number entered."
                    : "First tap arms; the second logs the bet."
              }
            >
              {busy ? "Saving…" : armed ? confirmLabel : "I took this"}
            </button>
            <span aria-live="polite" className="sr-only">
              {armed ? `Armed: ${confirmLabel}. Tap again to confirm.` : ""}
            </span>
          </>
        )}
      </div>
      {open && block !== null && (
        <p className="mt-1 text-xs text-[var(--warn)]">
          {blockReason(block, blockIsLive)}
        </p>
      )}
      {err !== null && <p className="mt-1 text-xs text-[var(--warn)]">{err}</p>}
      {warning !== null && (
        <p className="mt-1 text-xs text-[var(--warn)]">{warning}</p>
      )}
    </li>
  );
}

export default function BetSlip({
  slip,
  week,
  unitUsd,
}: {
  slip: Slip;
  week: number | null;
  unitUsd: number;
}) {
  const capUsed = slip.used >= slip.cap;
  return (
    <section
      id="bet-slip"
      className="bv-card mb-4 scroll-mt-4 p-4"
      aria-label="Bet slip"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-sm font-semibold text-[var(--text)]">
          {week === null ? "Bet slip" : `Bet slip · Week ${week}`}
        </h2>
        <span
          className={`font-mono text-xs ${capUsed ? "text-[var(--warn)]" : "text-[var(--text-dim)]"}`}
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
            <SlipRow key={r.gameId} r={r} unitUsd={unitUsd} />
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        Match the line and price to Hard Rock’s ticket before the second tap.
      </p>
    </section>
  );
}
