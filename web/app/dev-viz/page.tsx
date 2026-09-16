// DEV-ONLY comparison harness for the /dataviz audit. Never merged — it exists
// so the four visuals can be seen side by side, including BankrollCurve, which
// has no production data (zero graded picks in the whole database).
import BankrollCurve from "@/app/components/BankrollCurve";
import MovementChart from "@/app/components/MovementChart";
import MovementChartV1 from "@/app/components/MovementChartV1";
import MovementChartV2 from "@/app/components/MovementChartV2";
import MovementChartV3 from "@/app/components/MovementChartV3";
import { getMovements } from "@/lib/movement";

export const dynamic = "force-dynamic";

const GAME = 401864497; // UNLV @ Hawai'i — 12 books, the widest coverage we have

// A plausible settled season: 16 weeks off a $100 roll at $10 a unit.
const CURVE = [
  0, 10, -10, 20, 10, 30, 20, 40, 30, 50, 70, 60, 80, 70, 90, 110,
].map((d, i) => ({ week: i, units: d / 10, usd: 100 + d }));

function H({ n, t }: { n: string; t: string }) {
  return (
    <div className="mb-2 mt-8">
      <h2 className="font-[family-name:var(--font-display)] text-lg font-bold text-[var(--text)]">
        {n}
      </h2>
      <p className="text-xs text-[var(--text-dim)]">{t}</p>
    </div>
  );
}

export default async function DevViz() {
  const m = (await getMovements([GAME])).get(GAME) ?? null;
  const books = m?.books ?? [];
  const points = m?.points ?? [];
  return (
    <main className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="font-[family-name:var(--font-display)] text-2xl font-extrabold text-[var(--text)]">
        dataviz audit harness
      </h1>
      <p className="text-xs text-[var(--text-dim)]">
        {`Game ${GAME} · ${books.length} books · ${points.length} capture times`}
      </p>

      <H n="Movement — as it ships today" t="Six colours cycled across twelve books." />
      {points.length > 1 && <MovementChart points={points} books={books} />}

      <H n="Variant 1 — emphasise Hard Rock" t="One colour, one grey." />
      {points.length > 1 && <MovementChartV1 points={points} books={books} />}

      <H n="Variant 2 — categorical ramp, disjoint from the grades" t="Six named slots plus dashes; the tail folds to grey." />
      {points.length > 1 && <MovementChartV2 points={points} books={books} />}

      <H n="Variant 3 — Hard Rock against the market" t="Low–high band, market middle, Hard Rock on top." />
      {points.length > 1 && <MovementChartV3 points={points} books={books} />}

      <H n="Bankroll curve" t="Synthetic 16-week season — there is no graded pick in the database." />
      <BankrollCurve points={CURVE} startUsd={100} />
    </main>
  );
}
