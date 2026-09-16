"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { BoardFilters as Filters } from "@/lib/homeBoard";

// My-teams / Hard Rock filters for the board. Everything lives in the URL
// (?mine=1&hr=1) so a filtered board is a shareable link and the server does
// the filtering. The explainer line under the chips went on 2026-09-16: the
// chip labels say what they do, and the teams are the ones you follow.
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

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => toggleFlag("mine", current.myTeams)}
        aria-pressed={current.myTeams}
        className="bv-chip"
      >
        My teams
      </button>
      <button
        type="button"
        onClick={() => toggleFlag("hr", current.hrOnly)}
        aria-pressed={current.hrOnly}
        className="bv-chip"
      >
        Hard Rock line posted
      </button>
    </div>
  );
}
