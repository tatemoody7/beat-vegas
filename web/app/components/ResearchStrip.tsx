import Link from "next/link";
import type { HypothesisCard } from "@/lib/research";
import { HYPOTHESES } from "@/lib/research";

// The one-line research status above the Board (Tate, 2026-10-14: "the Board
// with a status strip above it"): how far the paper strategies are from their
// first decision, one pill per hypothesis with what it has logged, and the
// link to the Research page. It reads the stored Monday row like the cards do
// and never changes a rating; a visitor sees the same line.

const SHORT: Record<string, string> = {
  "H-ARM-1HU": "1H unders",
  "H-ARM-1HO": "1H overs",
  "H-ARM-FGU": "FG unders",
  "H-ARM-WX1H": "Wind 1H",
  "H-ARM-WXFG": "Wind FG",
  "H-ARM-HT1H": "60+ totals",
  "H-PRICE-HR": "Hard Rock pricing",
};

export function stripLine(cards: HypothesisCard[]): string {
  const arms = cards.filter((c) => c.meta.standard === "sprt");
  const read = arms.filter((c) => c.readAt !== null);
  const most = read.reduce((m, c) => Math.max(m, c.readings), 0);
  const needed = arms[0]?.needed ?? 30;
  const next = cards
    .map((c) => c.nextRead)
    .filter((d): d is string => !!d)
    .sort()[0];
  const head = `${arms.length} strategies on paper`;
  if (read.length === 0) return `${head} · not yet read`;
  const progress =
    most === 0
      ? `0 of ${needed} readings`
      : `up to ${most} of ${needed} readings`;
  return `${head} · ${progress}${next ? ` · next read ${next}` : ""}`;
}

export default function ResearchStrip({ cards }: { cards: HypothesisCard[] }) {
  if (cards.length === 0) return null;
  return (
    <div
      aria-label="Research status"
      className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-2)] px-3 py-2 text-xs"
    >
      <span className="font-semibold text-[var(--text)]">
        {stripLine(cards)}
      </span>
      {cards.map((c) => (
        <span
          key={c.meta.id}
          className="bv-pill"
          data-hypothesis={c.meta.id}
          title={`${c.meta.name}: ${c.status}`}
        >
          {`${SHORT[c.meta.id] ?? HYPOTHESES.find((h) => h.id === c.meta.id)?.name ?? c.meta.id} ${
            c.meta.standard === "pricing"
              ? `${c.readings} / ${c.needed}`
              : c.logged
          }`}
        </span>
      ))}
      <Link
        href="/research"
        className="ml-auto inline-flex min-h-6 items-center whitespace-nowrap font-semibold text-[var(--accent)] hover:underline"
      >
        Research →
      </Link>
    </div>
  );
}
