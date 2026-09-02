"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

// ?week= selector. `allowAll` adds an "All weeks" option (value "all").
export default function WeekSelect({
  weeks,
  current,
  allowAll = false,
}: {
  weeks: number[];
  current: number | "all";
  allowAll?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("week", e.target.value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
      Week
      <select value={String(current)} onChange={onChange} className="bv-select">
        {allowAll && <option value="all">All weeks</option>}
        {weeks.map((w) => (
          <option key={w} value={w}>
            {w}
          </option>
        ))}
      </select>
    </label>
  );
}
