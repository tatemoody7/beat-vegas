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

  // One filter at a time (Tate 2026-09-16): the two answer different
  // questions, and "my teams that Hard Rock has priced" is a view nobody asked
  // for. Turning one on turns the other off; clicking the active one clears it.
  function toggleFlag(key: "mine" | "hr", on: boolean) {
    push((p) => {
      p.delete("mine");
      p.delete("hr");
      if (!on) p.set(key, "1");
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
