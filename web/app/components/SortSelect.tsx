"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

export const SORTS = [
  { value: "rank", label: "Best lean first" },
  { value: "gap", label: "Biggest edge vs Vegas" },
  { value: "gapz", label: "Biggest edge (noise-adjusted)" },
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
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
      Sort
      <select value={current} onChange={onChange} className="bv-select">
        {SORTS.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  );
}
