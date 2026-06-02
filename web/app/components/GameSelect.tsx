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
    <label className="flex items-center gap-2 text-sm text-gray-400">
      Game
      <select
        value={current}
        onChange={onChange}
        className="max-w-xs rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100 focus:border-gray-500 focus:outline-none"
      >
        {games.map((g) => (
          <option key={g.id} value={g.id}>
            wk{g.week}: {g.matchup} ({g.snaps} snaps)
          </option>
        ))}
      </select>
    </label>
  );
}
