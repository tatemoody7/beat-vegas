import { utcFrom } from "@/lib/armPositions";
import { etClock12 } from "@/lib/et";
import { american, fmt } from "@/lib/format";
import {
  EV_CAVEAT,
  FEED_NOTE,
  evText,
  ordinal,
  scoringText,
  verdictText,
  type ShortlistEntry,
} from "@/lib/shortlist";

// The full analysis of a game on the Research top 10 (Tate 2026-10-15, Q14 +
// adjustments 3 and 4), at the top of its game page. Two blocks side by side:
// the FROZEN publication (rank, line, price, estimated EV, label, analysis,
// with its time) and the LATEST Hard Rock price with its own capture time;
// newer data never changes the frozen rank. Research wording only: estimates
// are called estimates, factors speak of scoring, and the Board's rank is
// named as a different ranking. Not a .bv-card: the page's first card is the
// decision, and stays so.

const prob = (x: number | null | undefined) =>
  x === null || x === undefined ? "—" : `${(100 * x).toFixed(1)}%`;

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2 text-sm">
      <dt className="w-32 shrink-0 text-[var(--text-dim)] sm:w-40">{k}</dt>
      <dd className="text-[var(--text)]">{v}</dd>
    </div>
  );
}

/** A local hour (e.g. 19.5) as a 24-hour clock, "~19:30 local". */
function localClock(h: number): string {
  const mins = Math.round(h * 60) % 1440;
  return `~${Math.floor(mins / 60)}:${String(mins % 60).padStart(2, "0")} local`;
}

function statValue(key: string, v: number | null): string {
  if (v === null) return "—";
  if (key === "fh_off_explosive") return `${(100 * v).toFixed(1)}%`;
  if (key === "fh_off_epa") return v.toFixed(3);
  return v.toFixed(1);
}

export default function ShortlistAnalysis({
  e,
  publishedAt,
  cardBuilt,
  boardRank,
  latest,
}: {
  e: ShortlistEntry;
  publishedAt: Date;
  cardBuilt: Date | null;
  boardRank: number | null;
  latest: {
    line: number | null;
    under: number | null;
    seenAt: string | null | undefined;
  };
}) {
  const p = e.price;
  const a = e.analysis;
  const s = a.situational;
  const w = a.weather;
  const latestText =
    latest.line === null || latest.under === null
      ? "no Hard Rock main line on file now"
      : `u${fmt(latest.line)} ${american(latest.under)}${latest.seenAt ? `, seen ${etClock12(utcFrom(latest.seenAt))}` : ""}`;
  const moved =
    e.first_hr && e.latest_hr
      ? `u${fmt(e.first_hr.line)} ${american(e.first_hr.under)} → u${fmt(e.latest_hr.line)} ${american(e.latest_hr.under)} (first seen ${etClock12(utcFrom(e.first_hr.at))})`
      : "—";

  return (
    <section
      aria-label="Research shortlist"
      className="rounded-lg border border-[var(--accent)]/40 bg-[var(--bg-2)] p-4"
    >
      <h2 className="text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--accent)]">
        {`Research shortlist R${e.rank} — research ranking, not the Board's rank`}
      </h2>
      <p className="mt-1 text-xs text-[var(--text-dim)]">
        {boardRank !== null
          ? `On the Board this game is #${boardRank}, by our model against the line; R${e.rank} ranks it by price.`
          : `R${e.rank} ranks it by price, not by our model.`}
      </p>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div
          data-testid="frozen"
          className="rounded-[var(--r-sm)] border border-[var(--border)] p-3"
        >
          <p className="text-xs font-semibold text-[var(--text)]">
            {`Published ${etClock12(publishedAt)} (frozen)`}
          </p>
          <p className="mt-1 font-mono text-sm text-[var(--text)]">
            {`u${fmt(p.hr_line)} ${american(p.hr_under)}`}
          </p>
          <p className="mt-1 text-sm text-[var(--text)]">{evText(p)}</p>
          <p className="mt-1">
            <span className="bv-badge bv-badge--push">{e.label}</span>
          </p>
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            {p.status === "priced"
              ? `${(p.ref_books ?? []).length} reference books in the same sweep, Hard Rock price confirmed ${p.hr_confirmed_at ? etClock12(utcFrom(p.hr_confirmed_at)) : "—"}`
              : `Incomplete pricing: ${p.status}.`}
          </p>
        </div>
        <div
          data-testid="latest"
          className="rounded-[var(--r-sm)] border border-[var(--border)] p-3"
        >
          <p className="text-xs font-semibold text-[var(--text)]">
            Latest Hard Rock price
          </p>
          <p className="mt-1 font-mono text-sm text-[var(--text)]">
            {latestText}
          </p>
          <p className="mt-1 text-xs text-[var(--text-dim)]">
            The frozen rank and estimate never change with it.
          </p>
        </div>
      </div>

      <p className="mt-3 text-sm text-[var(--text)]" data-testid="why">
        {e.why_rank}
      </p>

      <dl className="mt-3 flex flex-col gap-1">
        <Row k="Break-even" v={prob(p.breakeven)} />
        <Row k="Consensus fair under" v={prob(p.fair_under)} />
        <Row
          k="Best other book"
          v={
            p.best_other_under === null || p.best_other_under === undefined
              ? "—"
              : `${american(p.best_other_under)} at u${fmt(p.hr_line)}`
          }
        />
        <Row k="Hard Rock hold" v={prob(p.hr_hold)} />
        <Row k="Hard Rock line moves" v={moved} />
        <Row
          k="Model vs market"
          v={
            e.model.bv_line === null
              ? "no model number"
              : `our number ${fmt(e.model.bv_line)}, market ${fmt(e.model.market_line)} (context only, never a rank input)`
          }
        />
      </dl>

      <h3 className="mt-4 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-dim)]">
        The matchup, against every 2023-26 game
      </h3>
      <ul aria-label="Matchup stats" className="mt-1 flex flex-col">
        {a.stats.map((st) => (
          <li
            key={st.key}
            className="border-t border-[var(--border)] py-1.5 text-sm"
          >
            <p className="text-[var(--text-muted)]">{st.words}</p>
            <p className="text-[var(--text)]">
              <span className="font-mono">{statValue(st.key, st.value)}</span>
              {` · ${st.pct === null ? "no percentile" : `${ordinal(Math.round(100 * st.pct))} percentile`} · ${scoringText(st.scoring)}`}
              <span className="text-xs text-[var(--text-dim)]">
                {` · ${verdictText(st.verdict)}`}
              </span>
            </p>
          </li>
        ))}
      </ul>

      <dl className="mt-3 flex flex-col gap-1">
        <Row
          k="Rest"
          v={
            s.min_rest_days === null
              ? "—"
              : `shorter rest ${fmt(s.min_rest_days, 0)} days${s.either_off_bye ? " · a team is off a bye" : ""}${s.either_short_week ? " · a short week" : ""}`
          }
        />
        <Row
          k="Travel"
          v={
            s.away_travel_km === null
              ? "—"
              : `visitors travel ~${Math.round(s.away_travel_km * 0.621371)} miles`
          }
        />
        <Row
          k="Local kickoff"
          v={s.kick_local_hour === null ? "—" : localClock(s.kick_local_hour)}
        />
        <Row
          k="1H possessions (est.)"
          v={
            a.est_1h_possessions === null
              ? "—"
              : `${a.est_1h_possessions.toFixed(1)} combined (descriptive)`
          }
        />
        <Row
          k="Quarterbacks"
          v={a.qb.out ? `QB flagged out: ${a.qb.detail}` : a.qb.detail}
        />
        <Row
          k="Weather"
          v={
            w === null
              ? "no forecast on file"
              : w.dome
                ? "indoors"
                : `forecast wind ${fmt(w.wind_mph ?? null, 0)} mph (gust ${fmt(w.gust_mph ?? null, 0)}), ${fmt(w.temperature_f ?? null, 0)}°F, ${fmt(w.precipitation_mm ?? null, 1)} mm${w.scoring ? ` — ${scoringText(w.scoring)}` : ""}; ${verdictText(w.verdict)}`
          }
        />
      </dl>

      <p className="mt-3 text-xs text-[var(--text-dim)]">
        {`${EV_CAVEAT} Ranking key: the low end of the rough range, then the estimate, then the number of books; no factor carries weight (H-1H-FACTORS: none of 64 passed). ${FEED_NOTE}`}
      </p>
      {cardBuilt && (
        <p className="mt-1 text-xs text-[var(--text-dim)]">
          {`Matchup stats as known at the ${etClock12(cardBuilt)} build.`}
        </p>
      )}
    </section>
  );
}
