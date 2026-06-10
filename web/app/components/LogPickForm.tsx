"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { suggestedUnits } from "@/lib/kelly";
import type { SlateOption } from "@/lib/picks";

export default function LogPickForm({ slate }: { slate: SlateOption[] }) {
  const router = useRouter();
  const [gameId, setGameId] = useState(slate[0]?.gameId ?? 0);
  const [market, setMarket] = useState<"1H" | "full">("1H");
  // The line to default to for a game depends on the market: the 1H line for
  // first-half picks, the full-game total for full-game picks.
  const defaultLine = (gid: number, mkt: "1H" | "full") => {
    const g = slate.find((s) => s.gameId === gid);
    const v = mkt === "full" ? g?.fullGameLine : g?.curLine;
    return v ?? "";
  };
  const [line, setLine] = useState<string>(
    String(defaultLine(slate[0]?.gameId ?? 0, "1H")),
  );
  const [stake, setStake] = useState("1");
  const [price, setPrice] = useState("-110");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function onGameChange(gid: number) {
    setGameId(gid);
    setLine(String(defaultLine(gid, market))); // re-default to the new game's line
  }

  function onMarketChange(mkt: "1H" | "full") {
    setMarket(mkt);
    setLine(String(defaultLine(gameId, mkt))); // swap to that market's line
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (line.trim() === "" || !Number.isFinite(Number(line))) {
      setErr("Enter a line.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/picks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          gameId,
          market,
          line: Number(line),
          stake: Number(stake) || 1,
          price: Number(price) || -110,
          note,
        }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || `failed (${res.status})`);
      }
      setNote("");
      router.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "failed");
    } finally {
      setBusy(false);
    }
  }

  if (slate.length === 0) {
    return (
      <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
        No scored games this week — log picks once a slate is scored.
      </p>
    );
  }

  const field = "bv-input";
  const labelCls =
    "flex flex-col gap-1 text-xs font-medium text-[var(--text-muted)]";

  // Advisory fractional-Kelly stake hint: only for 1H picks where we have a
  // market no-vig fair-under to size the edge against the price you'd take.
  const selected = slate.find((s) => s.gameId === gameId);
  const fairUnder = market === "1H" ? (selected?.fairUnder ?? null) : null;
  const priceNum = Number(price);
  const kellyUnits =
    fairUnder != null && Number.isFinite(priceNum)
      ? suggestedUnits(fairUnder, priceNum)
      : 0;
  const kellyRounded = Math.round(kellyUnits * 2) / 2;

  return (
    <form onSubmit={submit} className="bv-card p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className={`${labelCls} sm:col-span-2`}>
          Game
          <select
            value={gameId}
            onChange={(e) => onGameChange(Number(e.target.value))}
            className={field}
          >
            {slate.map((g) => {
              const shown = market === "full" ? g.fullGameLine : g.curLine;
              const label = market === "full" ? "full-game" : "1H";
              return (
                <option key={g.gameId} value={g.gameId}>
                  {g.away} @ {g.home}
                  {shown !== null ? ` · ${label} line ${shown}` : ""}
                </option>
              );
            })}
          </select>
        </label>

        <label className={labelCls}>
          Market
          <select
            value={market}
            onChange={(e) => onMarketChange(e.target.value as "1H" | "full")}
            className={field}
          >
            <option value="1H">First half</option>
            <option value="full">Full game</option>
          </select>
        </label>
        <label className={labelCls}>
          {market === "full"
            ? "Your line (full game, under)"
            : "Your line (1H, under)"}
          <input
            type="number"
            step={0.5}
            value={line}
            onChange={(e) => setLine(e.target.value)}
            className={field}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className={labelCls} title="1 unit = one standard bet.">
            Stake (units)
            <input
              type="number"
              step={0.5}
              value={stake}
              onChange={(e) => setStake(e.target.value)}
              className={field}
            />
          </label>
          <label className={labelCls} title="The odds / price (e.g. −110).">
            Odds
            <input
              type="number"
              step={5}
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className={field}
            />
          </label>
        </div>

        {fairUnder != null && (
          <div className="sm:col-span-2 rounded-md border border-[var(--border)] bg-[color-mix(in_srgb,var(--accent)_6%,transparent)] px-3 py-2 text-xs">
            {kellyUnits > 0 ? (
              <span className="text-[var(--text-muted)]">
                Quarter-Kelly suggests{" "}
                <span className="font-mono font-semibold text-[var(--accent)]">
                  {kellyRounded.toFixed(1)} u
                </span>{" "}
                <span
                  title="Market no-vig fair-under at this number. Stake is advisory: quarter-Kelly, 1 unit = 1% of bankroll, capped at 3u."
                  className="underline decoration-dotted"
                >
                  (market fair under {(fairUnder * 100).toFixed(1)}%)
                </span>
                {kellyRounded > 0 && (
                  <button
                    type="button"
                    className="bv-nav-link ml-2"
                    onClick={() => setStake(String(kellyRounded))}
                  >
                    use {kellyRounded.toFixed(1)}u
                  </button>
                )}
              </span>
            ) : (
              <span className="text-[var(--text-muted)]">
                No +EV edge at {price} vs the market no-vig fair under{" "}
                {(fairUnder * 100).toFixed(1)}% — advisory stake 0u.
              </span>
            )}
          </div>
        )}

        <label className={`${labelCls} sm:col-span-2`}>
          Reason / note (why you took it — for later review)
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. both defenses elite, slow tempo, wind 18mph"
            className={field}
          />
        </label>
      </div>

      {err && (
        <p role="alert" className="mt-2 text-sm text-red-400">
          {err}
        </p>
      )}

      <button type="submit" disabled={busy} className="bv-btn mt-4">
        {busy ? "Logging…" : "Log pick"}
      </button>
    </form>
  );
}
