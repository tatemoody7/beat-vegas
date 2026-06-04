"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { MovementGame } from "@/lib/movement";

export default function GameSelect({
  games,
  current,
}: {
  games: MovementGame[];
  current: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("game", e.target.value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
      Game
      <select
        value={current}
        onChange={onChange}
        className="bv-select max-w-xs"
      >
        {games.map((g) => (
          <option key={g.id} value={g.id}>
            wk{g.week}: {g.matchup} ({g.snaps} updates)
          </option>
        ))}
      </select>
    </label>
  );
}
