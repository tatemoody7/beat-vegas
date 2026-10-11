import { unitColor } from "@/lib/format";
import {
  bandTable,
  coverage,
  headline,
  HIST_SCOPE,
  loadPostMortem,
  accuracyLine,
  loadModelAccuracy,
  type ModelAccuracy,
} from "@/lib/postmortem";
import { BREAKEVEN_PCT } from "@/lib/lineStudy";
import { BET_GAP_PTS, WEEKLY_BET_CAP } from "@/lib/verdict";
import GapLadderChart from "@/app/components/GapLadderChart";
import Glossary from "@/app/components/Glossary";
import RecordTable from "@/app/components/RecordTable";
import { EmptyLine } from "@/app/components/Section";
import Link from "next/link";

export const dynamic = "force-dynamic";

// How it works (2026-09-28, site review): the page a first-time visitor reads
// after the Board. What this is, how to read a row, where the bets are priced,
// the 2023–25 backtest labelled as a backtest, what we do not know, nine
// terms, and the helpline. It took over the research half of the old Track
// record page (/proof); the ledger half went to Results.
//
// The owner-only research section (the live season's diagnostic strip, the
// post-mortem's flags, the method fold, the line study) went with roadmap
// v2.0 (2026-10-11): the site is a public record and nothing more. Everyone
// reads the same page. Nothing here gates a bet.

const KEYS: { color: string; term: string; text: string }[] = [
  {
    color: "var(--good)",
    term: "Green",
    text: "a paper signal. The row says the line and price: “Paper signal: first-half under 24.5 at -110 on Hard Rock.” Since 2026-10-10 a visitor sees every rating before kickoff, in paper wording.",
  },
  {
    color: "var(--warn)",
    term: "Amber, “Not yet”",
    text: "close, but a line or price is missing. The row says what would make it a signal.",
  },
  {
    color: "var(--bad)",
    term: "Red, “Pass”",
    text: "the numbers do not disagree enough, or the line leans over. We only rate unders.",
  },
];

export default async function HowItWorksPage() {
  const [pm, acc] = await Promise.all([loadPostMortem(), loadModelAccuracy()]);

  const runs = pm?.runs ?? [];
  const buckets = pm?.buckets ?? [];
  const hist = runs.find((r) => r.scope === HIST_SCOPE);

  const lead =
    runs.length > 0
      ? headline(buckets, HIST_SCOPE, "fbs_only", "real", "cap5")
      : null;
  const pct0 = (v: number | null) =>
    v === null ? "—" : `${(100 * v).toFixed(0)}%`;
  const cov = coverage(buckets, HIST_SCOPE, "fbs_only");
  const gapReal = bandTable(
    buckets,
    HIST_SCOPE,
    "fbs_only",
    "real",
    "gap_band",
  );
  const computed = (hist?.computed_at ?? "").slice(0, 16).replace("T", " ");

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="bv-page-title mb-6">How it works</h1>

      <section aria-label="What this is" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What this is
        </h2>
        <p className="text-base leading-relaxed text-[var(--text-muted)]">
          <span className="text-[var(--text)]">
            Beat Vegas rates one bet: the college football first-half under.
          </span>{" "}
          Our model estimates first-half points without ever seeing the
          sportsbook line, so the gap between our number and the line is a real
          disagreement. When the gap is wide enough and the price is fair, it is
          a bet: one unit, at most {WEEKLY_BET_CAP} a week. We bet these
          ourselves and publish every one.
        </p>
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
          Best time to look: Friday after 5:30pm ET, and Saturday morning, once
          Hard Rock’s first-half lines are up.
        </p>
      </section>

      <section aria-label="Where bets are priced" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          Where bets are priced
        </h2>
        <p className="text-sm leading-relaxed text-[var(--text-muted)]">
          Every bet is priced at Hard Rock Bet, the only sportsbook in Florida.
          Your book’s first-half total may differ; the line and price to beat
          are the ones shown.
        </p>
      </section>

      {/* The backtest: the one historical number, headed as what it is, with
          the picture that explains it, in one card. */}
      <section
        aria-label="The finding"
        className="bv-card mb-8 grid grid-cols-1 gap-x-8 gap-y-6 p-5 lg:grid-cols-[1fr_1.5fr] lg:items-center"
      >
        {lead === null ? (
          <EmptyLine>
            The 2023–25 backtest is not computed yet. It runs after each
            morning’s grading.
          </EmptyLine>
        ) : (
          <div>
            <p className="bv-stat-label">
              {`Backtest, 2023–25 (not money bet) · first-half unders, ${WEEKLY_BET_CAP} a week`}
            </p>
            <p className="mt-2 font-[family-name:var(--font-display)] text-6xl font-extrabold leading-none tabular-nums text-[var(--text)]">
              {lead.hit}
            </p>
            <p className="mt-3 font-mono text-sm text-[var(--text-muted)]">
              {lead.record}
              {" · "}
              <span style={{ color: unitColor(lead.units) }}>
                {`${lead.units}u`}
              </span>
              {` · ROI ${lead.roi}`}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-[var(--text-dim)]">
              {`${lead.n} bets, could plausibly be ${pct0(lead.hitLo)}–${pct0(lead.hitHi)}. Hard Rock did not exist in these seasons. This is what the method would have returned, not money won.`}
            </p>
          </div>
        )}
        <div>
          <p className="bv-stat-label mb-1">
            The wider the gap, the more often the under wins
            {cov && (
              <span className="ml-2 font-normal normal-case tracking-normal">
                {`· ${cov.real.toLocaleString()} games at real closing lines`}
              </span>
            )}
          </p>
          <GapLadderChart rows={gapReal} breakeven={BREAKEVEN_PCT} />
        </div>
        <div className="lg:col-span-2">
          <RecordTable
            ariaLabel="Records at real closing lines"
            showInterval
            rows={[
              {
                key: "gap175",
                label: `2023–25, every gap ${BET_GAP_PTS}+`,
                note: "no weekly cap",
                rec:
                  runs.length > 0
                    ? headline(
                        buckets,
                        HIST_SCOPE,
                        "fbs_only",
                        "real",
                        "gap175",
                      )
                    : null,
                empty: "nothing graded yet",
              },
            ]}
          />
        </div>
      </section>

      <section aria-label="What we don’t know" className="mb-8 max-w-[68ch]">
        <h2 className="mb-2 text-lg font-semibold text-[var(--text)]">
          What we don’t know
        </h2>
        <div className="flex flex-col gap-3 text-sm leading-relaxed text-[var(--text-muted)]">
          <p>
            One first half is close to a coin flip. Our number misses a typical
            game by far more than any gap between it and the line, so a rating
            only means something across hundreds of bets.
          </p>
          {acc === null ? (
            <p>
              Hard Rock’s line has been at least as accurate as our number so
              far. The gap is a disagreement, not proof of who is right.
            </p>
          ) : (
            <ModelAccuracyBlock acc={acc} />
          )}
          <p>
            So the real test is the live record: Hard Rock’s actual lines, the
            bets we log, and whether the line moves our way after we bet. It is
            on{" "}
            <Link
              href="/results"
              className="inline-flex min-h-6 items-center text-[var(--accent)] hover:underline"
            >
              Results
            </Link>
            . Until that record is large, read every rating as an opinion with a
            number on it.
          </p>
        </div>
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

// The model against Hard Rock, in public (Tate's call 2026-10-07): the average
// miss of each over this season's graded games, the same games for both. The
// sentence follows the numbers so it can never claim the wrong side.
function ModelAccuracyBlock({ acc }: { acc: ModelAccuracy }) {
  const a = accuracyLine(acc);
  const verdict =
    a.closer === "hardRock"
      ? "Hard Rock’s line has been closer than our number so far."
      : a.closer === "ours"
        ? "Our number has been closer than Hard Rock’s line so far, by a margin that small samples swing."
        : "Our number and Hard Rock’s line have been equally close so far.";
  return (
    <div>
      <p>
        {`${verdict} The gap is a disagreement, not proof of who is right.`}
      </p>
      <div
        role="group"
        aria-label="Average miss this season"
        className="mt-3 max-w-sm"
      >
        <p className="bv-stat-label">
          {`Average miss, first half · ${acc.season} · ${acc.n} games`}
        </p>
        <div className="mt-1 grid grid-cols-2 gap-x-6">
          <p>
            <span className="block font-mono text-2xl tabular-nums text-[var(--text)]">
              {`${a.ours} pts`}
            </span>
            <span className="text-xs text-[var(--text-dim)]">Our number</span>
          </p>
          <p>
            <span className="block font-mono text-2xl tabular-nums text-[var(--text)]">
              {`${a.hardRock} pts`}
            </span>
            <span className="text-xs text-[var(--text-dim)]">
              Hard Rock’s line
            </span>
          </p>
        </div>
      </div>
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        Lower is closer. Each game counts at the number we published that week.
      </p>
    </div>
  );
}
