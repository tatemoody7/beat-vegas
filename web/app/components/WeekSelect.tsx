"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

export default function WeekSelect({
  weeks,
  current,
}: {
  weeks: number[];
  current: number;
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
      <select value={current} onChange={onChange} className="bv-select">
        {weeks.map((w) => (
          <option key={w} value={w}>
            {w}
          </option>
        ))}
      </select>
    </label>
  );
}
