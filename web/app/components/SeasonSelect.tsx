"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

// ?season= selector. `allowAll` adds an "All seasons" option (value "all").
export default function SeasonSelect({
  seasons,
  current,
  allowAll = false,
}: {
  seasons: number[];
  current: number | "all";
  allowAll?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  function onChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const next = new URLSearchParams(params.toString());
    next.set("season", e.target.value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[var(--text-dim)]">
      Season
      <select value={String(current)} onChange={onChange} className="bv-select">
        {allowAll && <option value="all">All seasons</option>}
        {seasons.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </label>
  );
}
