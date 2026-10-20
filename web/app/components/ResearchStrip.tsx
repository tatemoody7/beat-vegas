import Link from "next/link";
import { etDateLabel } from "@/lib/et";
import type { HypothesisCard } from "@/lib/research";

// The one slim line above the Board (Tate, 2026-10-15, Q1; it replaced the
// intro note and the pill strip of 2026-10-14): what this is, how far the paper
// strategies are from their first decision, and the link to Research. It reads
// the stored Monday row like the cards do and never changes a rating; a visitor
// sees the same line.

const COUNT_WORDS = [
  "no",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
];

export function stripLine(cards: HypothesisCard[]): string {
  const arms = cards.filter((c) => c.meta.standard === "sprt");
  const read = arms.filter((c) => c.readAt !== null);
  const most = read.reduce((m, c) => Math.max(m, c.readings), 0);
  const needed = arms[0]?.needed ?? 30;
  const next = cards
    .map((c) => c.nextRead)
    .filter((d): d is string => !!d)
    .sort()[0];
  const head = `${COUNT_WORDS[arms.length] ?? arms.length} paper ${arms.length === 1 ? "strategy" : "strategies"} judged against the closing price`;
  if (read.length === 0) return `${head} · not yet read`;
  const progress =
    most === 0
      ? `0 of ${needed} readings`
      : `up to ${most} of ${needed} readings`;
  return `${head} · ${progress}${next ? ` · next read ${etDateLabel(next)}` : ""}`;
}

/** The slim line's fixed opening (Tate 2026-10-15, Q1); the strategies are
 *  named by what they are, not by one of them (D4 build 5, 2026-10-20). */
export const SLIM_LEAD = "Research season";

export default function ResearchStrip({ cards }: { cards: HypothesisCard[] }) {
  return (
    <p
      aria-label="Research status"
      className="mb-4 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-[var(--text-muted)]"
    >
      <span>
        {cards.length > 0 ? `${SLIM_LEAD} · ${stripLine(cards)}` : SLIM_LEAD}
      </span>
      <Link
        href="/research"
        className="inline-flex min-h-6 items-center whitespace-nowrap font-semibold text-[var(--accent)] hover:underline"
      >
        Research →
      </Link>
    </p>
  );
}
