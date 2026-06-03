"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { SlateOption } from "@/lib/picks";

export default function LogPickForm({ slate }: { slate: SlateOption[] }) {
  const router = useRouter();
  const [gameId, setGameId] = useState(slate[0]?.gameId ?? 0);
  const lineFor = (gid: number) =>
    slate.find((g) => g.gameId === gid)?.curLine ?? "";
  const [line, setLine] = useState<string>(String(lineFor(slate[0]?.gameId ?? 0)));
  const [stake, setStake] = useState("1");
  const [price, setPrice] = useState("-110");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function onGameChange(gid: number) {
    setGameId(gid);
    setLine(String(lineFor(gid))); // re-default the line to the new game's line
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
      <p className="rounded-lg border border-gray-800 bg-gray-900 p-4 text-sm text-gray-400">
        No scored games this week — log picks once a slate is scored.
      </p>
    );
  }

  const field = "rounded-md border border-gray-700 bg-gray-900 px-2 py-1.5 text-gray-100 focus:border-gray-500 focus:outline-none";

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-gray-800 bg-gray-950 p-4"
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-gray-400 sm:col-span-2">
          Game
          <select
            value={gameId}
            onChange={(e) => onGameChange(Number(e.target.value))}
            className={field}
          >
            {slate.map((g) => (
              <option key={g.gameId} value={g.gameId}>
                {g.away} @ {g.home} · under score {g.underScore ?? "—"} · line{" "}
                {g.curLine ?? "—"}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Your line (under)
          <input
            type="number"
            step={0.5}
            value={line}
            onChange={(e) => setLine(e.target.value)}
            className={field}
          />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-xs text-gray-400" title="1 unit = one standard bet.">
            Stake (units)
            <input
              type="number"
              step={0.5}
              value={stake}
              onChange={(e) => setStake(e.target.value)}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-400" title="The odds / price (e.g. −110).">
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

        <label className="flex flex-col gap-1 text-xs text-gray-400 sm:col-span-2">
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

      {err && <p className="mt-2 text-sm text-red-400">{err}</p>}

      <button
        type="submit"
        disabled={busy}
        className="mt-3 rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
      >
        {busy ? "Logging…" : "Log pick"}
      </button>
    </form>
  );
}
