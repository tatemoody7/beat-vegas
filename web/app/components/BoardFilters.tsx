"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { BoardFilters as Filters } from "@/lib/homeBoard";

// The Hard Rock filter for the board. It lives in the URL (?hr=1) so a
// filtered board is a shareable link and the server does the filtering. The
// owner's "My teams" chip went with roadmap v2.0 (2026-10-11: the site is a
// public record and nothing more); `?mine=1` still parses server-side.
export default function BoardFilters({ current }: { current: Filters }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function toggleHr(on: boolean) {
    const next = new URLSearchParams(params.toString());
    next.delete("mine");
    next.delete("hr");
    if (!on) next.set("hr", "1");
    const qs = next.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => toggleHr(current.hrOnly)}
        aria-pressed={current.hrOnly}
        className="bv-chip"
      >
        Hard Rock line posted
      </button>
    </div>
  );
}
