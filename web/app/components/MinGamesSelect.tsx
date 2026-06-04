"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

const OPTIONS = [5, 10, 15, 20, 25, 30, 40, 50, 60];

export default function MinGamesSelect({ current }: { current: number }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("minGames", e.target.value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
      Min games / line
      <select value={current} onChange={onChange} className="bv-select">
        {OPTIONS.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </label>
  );
}
