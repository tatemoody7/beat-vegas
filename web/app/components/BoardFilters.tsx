"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { MY_TEAMS, type BoardFilters as Filters } from "@/lib/homeBoard";

// My-teams / Hard Rock filters for the board. The DAY filter moved to
// WeekStrip, which shows the counts as well — two controls for one job was one
// too many. Everything still lives in the URL (?mine=1&hr=1) so a filtered
// board is a shareable link and the server does the filtering. What each toggle
// does is said in a visible line, not a `title=` a phone cannot show (spec §12).
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
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => toggleFlag("mine", current.myTeams)}
          aria-pressed={current.myTeams}
          className={chip(current.myTeams)}
        >
          My teams
        </button>
        <button
          type="button"
          onClick={() => toggleFlag("hr", current.hrOnly)}
          aria-pressed={current.hrOnly}
          className={chip(current.hrOnly)}
        >
          Hard Rock line posted
        </button>
      </div>
      <p className="text-xs text-[var(--text-dim)]">
        {`My teams: only ${MY_TEAMS.join(", ")}. Hard Rock line posted: the only games you can bet today.`}
      </p>
    </div>
  );
}
