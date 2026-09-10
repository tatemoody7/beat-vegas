"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { DaySummary } from "@/lib/homeBoard";

// Thu-Sun across the top of the board: how many games each day carries and
// where the bets sit, so Saturday's load is obvious before any scrolling. It is
// also the day filter — the separate "Day" pill row is gone, since two controls
// for one job is one too many.
//
// State lives in the URL (?days=sat,sun) so a filtered board stays a shareable
// link and the server does the filtering.

export default function WeekStrip({
  days,
  current,
}: {
  days: DaySummary[];
  current: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function toggle(day: string) {
    const on = current.includes(day);
    const next = on ? current.filter((d) => d !== day) : [...current, day];
    const p = new URLSearchParams(params.toString());
    if (next.length === 0) p.delete("days");
    else p.set("days", next.join(","));
    const qs = p.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  if (days.length === 0) return null;

  return (
    <div className="mb-3">
      <div className="flex flex-wrap gap-2">
        {days.map((d) => {
          const on = current.includes(d.day);
          return (
            <button
              key={d.day}
              type="button"
              onClick={() => toggle(d.day)}
              aria-pressed={on}
              className={`flex min-w-20 flex-col items-start rounded-md border px-3 py-2 text-left transition-colors ${
                on
                  ? "border-[var(--accent-strong)] bg-[var(--accent-soft)]"
                  : "border-[var(--border)] hover:border-[var(--border-strong)]"
              }`}
            >
              <span
                className={`text-xs font-semibold uppercase tracking-wide ${
                  on ? "text-[var(--accent)]" : "text-[var(--text-muted)]"
                }`}
              >
                {d.label}
              </span>
              <span className="font-mono text-sm text-[var(--text)]">
                {d.games}
              </span>
              <span
                className="text-[0.65rem]"
                style={{
                  color: d.bets > 0 ? "var(--good)" : "var(--text-dim)",
                }}
              >
                {d.bets > 0
                  ? `${d.bets} ${d.bets === 1 ? "bet" : "bets"}`
                  : "no bets"}
              </span>
            </button>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-[var(--text-dim)]">
        {current.length > 0
          ? "Showing the days you picked. Tap again to clear."
          : "Games per day, and where the bets are. Tap a day to filter."}
      </p>
    </div>
  );
}
