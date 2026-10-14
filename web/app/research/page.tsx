import Link from "next/link";
import ArmCard from "@/app/components/ArmCard";
import Glossary from "@/app/components/Glossary";
import { getArmPositions } from "@/lib/armPositions";
import { PROTOCOL, cardsFor } from "@/lib/research";
import hypotheses from "../../data/hypotheses.json";

export const dynamic = "force-dynamic";

// Research (2026-10-14, programme step 11; Tate's calls in the whole-system
// review): the public record of what is being tested. One card per registered
// hypothesis from the stored Monday read (lib/armPositions.ts: never
// recomputed), the protocol in plain words, every closed hypothesis with its
// verdict (web/data/hypotheses.json, exported from docs/HYPOTHESES.md and
// parity-tested), how to read the Board, and the glossary. It replaced How it
// works; the 2023-25 backtest card went with it (the 2026 factor screen found
// the gap predicts nothing against the close). The Board is still the home
// page; this page never changes what it shows.

const KEYS: { color: string; term: string; text: string }[] = [
  {
    color: "var(--good)",
    term: "Green",
    text: "a paper signal. The row says the line and price: “Paper signal: first-half under 24.5 at -110 on Hard Rock.” A visitor sees every rating before kickoff, in paper wording.",
  },
  {
    color: "var(--warn)",
    term: "Amber, “Not yet”",
    text: "close, but a line or price is missing. The row says what would make it a signal.",
  },
  {
    color: "var(--bad)",
    term: "Red, “Pass”",
    text: "the numbers do not disagree enough, or the line leans the other way.",
  },
];

type Row = {
  id: string;
  question: string;
  status: string;
  family: string;
  doc: string;
};

const CLOSED: Record<string, string> = {
  "tested-null": "tested, no edge",
  rejected: "rejected",
  superseded: "superseded",
  "tested-positive": "tested, positive",
  adopted: "adopted",
};

const docName = (doc: string) => {
  const m = doc.match(/`([^`]+\.md)`/);
  return m ? m[1].replace(/^docs\//, "") : null;
};

export default async function ResearchPage() {
  const positions = await getArmPositions();
  const cards = cardsFor(positions);
  const rows = hypotheses as Row[];
  const closed = rows.filter((r) => r.status in CLOSED);
  const exploratory = rows.filter((r) => r.status === "exploratory");

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="bv-page-title mb-2">Research</h1>
      <p className="bv-page-sub mb-6">
        What is being tested, how each test is judged, and where it stands.
      </p>

      <section aria-label="What this is" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What this is
        </h2>
        <p className="text-sm leading-relaxed text-[var(--text-muted)]">
          Beat Vegas is a college football research lab. Every strategy runs on
          paper and is judged by one number: the value of each wager against the
          books’ vig-free closing line, read at Hard Rock’s price. The Board
          keeps showing the first-half under ratings for anyone who follows the
          games; this page is the record of whether any of it holds up.
        </p>
      </section>

      <section aria-label="The strategies on paper" className="mb-8">
        <h2 className="mb-1 text-lg font-semibold text-[var(--text)]">
          The strategies on paper
        </h2>
        <p className="mb-3 max-w-[68ch] text-sm leading-relaxed text-[var(--text-muted)]">
          Each card shows its own standard. A paper strategy needs{" "}
          {PROTOCOL.NEEDED_READINGS} readings over {PROTOCOL.MIN_WEEKS} or more
          weeks before it can be promoted or stopped; the pricing study needs{" "}
          {PROTOCOL.PRICING_NEEDED} forward opportunities before it reads a
          direction. Nothing is ranked until then.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          {cards.map((c) => (
            <ArmCard key={c.meta.id} card={c} />
          ))}
        </div>
      </section>

      <section
        aria-label="How a strategy is judged"
        className="mb-8 max-w-[68ch]"
      >
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          How a strategy is judged
        </h2>
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-[var(--text-muted)]">
          <p>
            A reading is one paper pick with a usable closing line: the median
            of the other books’ lines inside two hours of kickoff, with the vig
            removed, converted to the exact number Hard Rock offered. The pick’s
            value is what that fair line says the wager was worth at Hard Rock’s
            price. A pick with no usable close is counted as excluded, never as
            a reading.
          </p>
          <p>
            Each week’s readings are averaged, and the weeks feed a sequential
            test that asks whether the strategy’s value is{" "}
            {`${Math.round(100 * PROTOCOL.TARGET_EV)}%`} or better. No decision
            is read before {PROTOCOL.NEEDED_READINGS} readings over{" "}
            {PROTOCOL.MIN_WEEKS} weeks. A strategy that crosses the upper
            boundary is promoted to a small live validation; one that crosses
            the lower boundary stops, which means “needs more evidence”, not “no
            edge”; one still undecided after {PROTOCOL.MAX_READINGS} readings or
            the season’s end times out. Every ending spends part of a fixed
            error budget, so the number of strategies tested is limited by
            design.
          </p>
          <p>
            The pricing study is different: it asks whether Hard Rock’s price is
            ever better than the market’s fair price for the same wager, and
            whether the market then moves toward Hard Rock. It reads a direction
            only after {PROTOCOL.PRICING_NEEDED} such opportunities since the
            rule was frozen.
          </p>
          <p>
            The owner also bets first-half unders with real money as a personal
            stake. That record is on{" "}
            <Link
              href="/results"
              className="inline-flex min-h-6 items-center text-[var(--accent)] hover:underline"
            >
              Results
            </Link>
            , labelled as a personal stake, and is never evidence for any
            strategy.
          </p>
        </div>
      </section>

      <section aria-label="Closed hypotheses" className="mb-8">
        <h2 className="mb-1 text-lg font-semibold text-[var(--text)]">
          Closed hypotheses
        </h2>
        <p className="mb-3 max-w-[68ch] text-sm leading-relaxed text-[var(--text-muted)]">
          Every idea tested or proposed against the data, with its verdict, from
          the registry. Results from before a strategy was registered are
          development evidence: they shaped the rule and can never count for it.
        </p>
        <div className="bv-table-wrap">
          <table className="w-full text-sm" aria-label="Closed hypotheses">
            <thead>
              <tr className="text-left text-[0.65rem] uppercase tracking-[0.08em] text-[var(--text-dim)]">
                <th className="py-1 pr-3 font-semibold">Id</th>
                <th className="py-1 pr-3 font-semibold">Question</th>
                <th className="py-1 pr-3 font-semibold">Verdict</th>
                <th className="py-1 font-semibold">Where</th>
              </tr>
            </thead>
            <tbody>
              {closed.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-[var(--border)] align-top text-[var(--text-muted)]"
                >
                  <td className="py-1.5 pr-3 font-mono text-xs text-[var(--text)]">
                    {r.id}
                  </td>
                  <td className="py-1.5 pr-3">{r.question}</td>
                  <td className="py-1.5 pr-3 whitespace-nowrap">
                    {CLOSED[r.status]}
                  </td>
                  <td className="py-1.5 font-mono text-xs">
                    {docName(r.doc) ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {exploratory.length > 0 && (
          <p className="mt-2 text-xs text-[var(--text-dim)]">
            {`${exploratory.length} exploratory rows (measurements that decide nothing) are listed in the registry and not here.`}
          </p>
        )}
      </section>

      <section aria-label="How to read the Board" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          How to read the Board
        </h2>
        <ul className="flex flex-col gap-2">
          {KEYS.map((k) => (
            <li
              key={k.term}
              className="grid grid-cols-[14px_1fr] items-baseline gap-2.5 text-sm text-[var(--text-muted)]"
            >
              <span
                aria-hidden="true"
                className="mt-1 inline-block h-3 w-3 rounded-[3px]"
                style={{ background: k.color }}
              />
              <span>
                <span className="font-semibold text-[var(--text)]">
                  {k.term}
                </span>
                {` — ${k.text}`}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm leading-relaxed text-[var(--text-muted)]">
          Every rating is priced at Hard Rock Bet. Your book’s first-half total
          may differ; the line and price to beat are the ones shown. Best time
          to look: Friday after 5:30pm ET, and Saturday morning, once Hard
          Rock’s first-half lines are up.
        </p>
      </section>

      <section aria-label="What we don’t know" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What we don’t know
        </h2>
        <p className="text-sm leading-relaxed text-[var(--text-muted)]">
          One first half is close to a coin flip. Our number misses a typical
          game by far more than any gap between it and the line, and Hard Rock’s
          line has been at least as accurate as our number so far. The gap is a
          disagreement, not proof of who is right; a rating only means something
          across hundreds of readings, which is what the cards above are
          counting toward.
        </p>
      </section>

      <Glossary />

      <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Link href="/records" className="bv-btn">
          Every game we have rated →
        </Link>
        <p className="text-xs text-[var(--text-dim)]">
          If gambling is a problem for you or someone you know, call
          1-833-PLAYWISE.
        </p>
      </div>
    </div>
  );
}
