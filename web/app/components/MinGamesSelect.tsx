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
    <label className="flex items-center gap-2 text-sm text-gray-400">
      Min games / line
      <select
        value={current}
        onChange={onChange}
        className="rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100 focus:border-gray-500 focus:outline-none"
      >
        {OPTIONS.map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </label>
  );
}
