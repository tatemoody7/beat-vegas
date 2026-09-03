"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  DAY_LABEL,
  DAYS,
  MY_TEAMS,
  type BoardFilters as Filters,
} from "@/lib/homeBoard";

// Day / my-teams / Hard Rock filters for the board. Everything lives in the URL
// (?days=sat,sun&mine=1&hr=1) so a filtered board is a shareable link and the
// server does the filtering.
export default function BoardFilters({ current }: { current: Filters }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function push(mut: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(params.toString());
    mut(next);
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  function toggleDay(day: string) {
    const on = current.days.includes(day);
    const days = on
      ? current.days.filter((d) => d !== day)
      : [...current.days, day];
    push((p) => {
      if (days.length === 0) p.delete("days");
      else p.set("days", days.join(","));
    });
  }

  function toggleFlag(key: "mine" | "hr", on: boolean) {
    push((p) => {
      if (on) p.delete(key);
      else p.set(key, "1");
    });
  }

  const chip = (on: boolean) =>
    `rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
      on
        ? "border-[var(--accent-strong)] bg-[var(--accent-soft)] text-[var(--accent)]"
        : "border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)]"
    }`;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
        Day
      </span>
      {DAYS.map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => toggleDay(d)}
          aria-pressed={current.days.includes(d)}
          className={chip(current.days.includes(d))}
        >
          {DAY_LABEL[d]}
        </button>
      ))}
      <button
        type="button"
        onClick={() => toggleFlag("mine", current.myTeams)}
        aria-pressed={current.myTeams}
        className={chip(current.myTeams)}
        title={`Only games involving ${MY_TEAMS.join(", ")}.`}
      >
        My teams
      </button>
      <button
        type="button"
        onClick={() => toggleFlag("hr", current.hrOnly)}
        aria-pressed={current.hrOnly}
        className={chip(current.hrOnly)}
        title="Only games Hard Rock has posted a first-half line for — the only ones you can bet today."
      >
        Hard Rock line posted
      </button>
    </div>
  );
}
