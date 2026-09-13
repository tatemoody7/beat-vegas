import type { ReactNode } from "react";

// A collapsed section. Track record was 9,159px of 19 stacked blocks and Tate
// did not read it (2026-09-13); the fix is not to delete the analysis but to
// stop making the whole of it the price of admission. The verdict, the gap
// ladder and the live season stay open; methodology, calibration, the
// estimated-basis block and the line study live in here.
//
// A native <details> on purpose: it works with no JavaScript, it is keyboard
// and screen-reader correct for free, and the browser's find-in-page opens it.
// Same element the glossary already uses at the foot of this page.
export default function Fold({
  title,
  hint,
  children,
  defaultOpen = false,
}: {
  title: string;
  /** One line saying what is inside, so the summary is a decision not a guess. */
  hint?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="mt-4 border-t border-[var(--border)] pt-4"
    >
      <summary className="flex min-h-11 cursor-pointer items-center gap-2">
        <span className="text-sm font-semibold text-[var(--text)]">
          {title}
        </span>
        {hint && <span className="text-xs text-[var(--text-dim)]">{hint}</span>}
        <span
          aria-hidden="true"
          className="ml-auto text-xs text-[var(--text-dim)]"
        >
          ▾
        </span>
      </summary>
      <div className="mt-3">{children}</div>
    </details>
  );
}
