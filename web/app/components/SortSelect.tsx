"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const SORTS = [
  { value: "rank", label: "Model rank" },
  { value: "gap", label: "Biggest gaps" },
  { value: "gapz", label: "Biggest gaps (noise-adj)" },
] as const;

export default function SortSelect({ current }: { current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("sort", e.target.value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-sm text-gray-400">
      Sort
      <select
        value={current}
        onChange={onChange}
        className="rounded-md border border-gray-700 bg-gray-900 px-2 py-1 text-gray-100 focus:border-gray-500 focus:outline-none"
      >
        {SORTS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );
}
