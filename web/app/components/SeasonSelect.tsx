"use client";

import { useRouter, useSearchParams } from "next/navigation";

export default function SeasonSelect({
  seasons,
  current,
}: {
  seasons: number[];
  current: number;
}) {
  const router = useRouter();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("season", e.target.value);
    router.push(`/?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-sm text-gray-400">
      Season
      <select
        value={current}
        onChange={onChange}
        className="rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100 focus:border-gray-500 focus:outline-none"
      >
        {seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}
