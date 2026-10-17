import Link from "next/link";

import {
  labelOf,
  RESULT_COLOR,
  RESULT_PENDING,
  RESULT_TEXT,
} from "@/lib/labels";
import {
  defaultWeek,
  getRecordSeasons,
  getSeasonRecords,
  viewTotals,
  type RecordRow,
} from "@/lib/records";
import { american } from "@/lib/format";
import { resolveSeason } from "@/lib/season";
import { viewerIsAuthed } from "@/lib/session";
import { gateRecords } from "@/lib/signalGate";
import { barRule } from "@/lib/glossary";
import { getScheduledCard } from "@/lib/card";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import { EmptyLine } from "@/app/components/Section";

export const dynamic = "force-dynamic";

// Two records, never mixed (fact-check audit 2026-10-17, Tate): Hard Rock
// Records grade each game on Hard Rock's own first-half line and price as the
// last scheduled card froze them -- what could actually have been bet -- and
// Market Research grades it on the consensus close, a benchmark no one could
// bet. A game with no verified Hard Rock line reads so and stays out of every
// Hard Rock figure; nothing substitutes a median or consensus line for it.
type View = "hr" | "market";

const NO_HR_LINE = "No verified Hard Rock line";
const NO_CLOSE = "No consensus close";

// The legend IS the explanation of the columns — a `title=` on a header is
// invisible on a phone, so the table carries none (spec §25.10).
const LEGEND: Record<View, [string, string][]> = {
  hr: [
    ["Full game", "the full-game total the books posted"],
    [
      "Our number",
      "our own first-half estimate; it never sees the sportsbook line",
    ],
    [
      "Hard Rock",
      "Hard Rock's first-half line and under price on the last scheduled card before kickoff — what could have been bet",
    ],
    [
      "Gap",
      "Hard Rock's line minus our number. Positive means the line is above us, which leans under",
    ],
    [
      "Scored after",
      "our number for that game was produced after kickoff (a re-score of a played week). It counts for accuracy, never as a bet we could have made",
    ],
  ],
  market: [
    ["Full game", "the full-game total the books posted"],
    [
      "Our number",
      "our own first-half estimate; it never sees the sportsbook line",
    ],
    [
      "Close",
      "the middle of three or more other books' first-half lines in the two hours before kickoff (Hard Rock and Fliff left out). A research benchmark, not a line anyone could bet, so it has no price",
    ],
    ["Gap", "the close minus our number"],
    [
      "Scored after",
      "our number for that game was produced after kickoff (a re-score of a played week)",
    ],
  ],
};

function fmt(v: number | null, digits = 1): string {
  return v === null ? "—" : v.toFixed(digits);
}

function gapText(v: number | null): string {
  return v === null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(1)}`;
}

function resultText(r: RecordRow, view: View): string {
  const line = view === "hr" ? r.hrLine : r.consLine;
  const out = view === "hr" ? r.hrOutcome : r.consOutcome;
  if (line === null) {
    if (r.firstHalfTotal === null) return RESULT_PENDING;
    return view === "hr" ? NO_HR_LINE : NO_CLOSE;
  }
  return labelOf(RESULT_TEXT, out, RESULT_PENDING);
}

export default async function RecordsPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string; view?: string }>;
}) {
  const seasons = await getRecordSeasons();
  const sp = await searchParams;
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  // Our number, the gaps and the rank stay blank for a visitor until kickoff
  // (research season, lib/signalGate). Totals read only played games.
  const raw: RecordRow[] = seasons.length ? await getSeasonRecords(season) : [];
  const all = gateRecords(raw, await viewerIsAuthed(), new Date());

  // A season with no Hard Rock line on file (everything before the 2026 cards)
  // opens on Market Research; its Hard Rock tab says why it is empty.
  const hasHr = raw.some((r) => r.hrLine !== null);
  const view: View =
    sp.view === "market" || sp.view === "hr"
      ? sp.view
      : hasHr
        ? "hr"
        : "market";
  const totals = viewTotals(raw, view);

  // ONE WEEK AT A TIME (Tate 2026-09-13); the download hands over the season.
  const weeks = [...new Set(all.map((r) => r.week))]
    .filter((w): w is number => typeof w === "number")
    .sort((a, b) => a - b);
  const reqWeek = Number(sp.week);
  const week =
    Number.isInteger(reqWeek) && weeks.includes(reqWeek)
      ? reqWeek
      : (defaultWeek(all) ?? weeks[weeks.length - 1] ?? null);
  const rows = week === null ? all : all.filter((r) => r.week === week);
  // The week's bar, from its newest SCHEDULED card (the Board's own).
  const card = week === null ? null : await getScheduledCard(season, week);
  const barText = barRule(card?.slate?.bar ?? null, week);
  const href = (o: { season?: number; week?: number | null; view?: View }) => {
    const q = new URLSearchParams();
    q.set("season", String(o.season ?? season));
    const w = o.week === undefined ? week : o.week;
    if (w !== null) q.set("week", String(w));
    q.set("view", o.view ?? view);
    return `/records?${q.toString()}`;
  };

  const rec = totals.record;
  const totalsLine =
    view === "hr"
      ? !hasHr
        ? `No Hard Rock lines exist for ${season}: they were first recorded with the 2026 cards. See Market Research.`
        : rec === null
          ? `Nothing graded at Hard Rock's line in ${season} yet.`
          : `${season} at Hard Rock's line on the last scheduled card: ${rec.record} · ${rec.units} units at Hard Rock's price · ROI ${rec.roi} · ${totals.graded} games verified; ${totals.missing} without a verified Hard Rock line.`
      : rec === null
        ? `Nothing graded at the consensus close in ${season} yet.`
        : `${season} at the consensus close (a research benchmark, not a bet): ${rec.record} · unders ${rec.hit}${
            rec.hitLo !== null && rec.hitHi !== null
              ? ` (plausibly ${Math.round(rec.hitLo * 100)}%–${Math.round(rec.hitHi * 100)}%)`
              : ""
          } · ${totals.graded} games; ${totals.missing} without a usable close.`;

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="bv-page-title">Every game we have rated</h1>
      <p className="bv-page-sub mb-1">
        Our number and how the first half actually landed, graded two ways that
        are never mixed. Download it if you want your own copy.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {seasons.map((s) => (
          <Link
            key={s}
            href={`/records?season=${s}`}
            className={`bv-pill ${s === season ? "ring-1 ring-[var(--accent)]" : ""}`}
          >
            <span className="bv-pill-value">{s}</span>
          </Link>
        ))}
        <a
          href={`/api/records?season=${season}`}
          className="bv-btn ml-auto"
          download
        >
          {`Download all of ${season}`}
        </a>
      </div>

      <div
        role="tablist"
        aria-label="Which record"
        className="mb-3 flex flex-wrap gap-2"
      >
        {(
          [
            ["hr", "Hard Rock Records"],
            ["market", "Market Research"],
          ] as [View, string][]
        ).map(([v, label]) => (
          <Link
            key={v}
            role="tab"
            aria-selected={v === view}
            href={href({ view: v })}
            className={`bv-pill ${v === view ? "ring-1 ring-[var(--accent)]" : ""}`}
          >
            <span className="bv-pill-value">{label}</span>
          </Link>
        ))}
      </div>
      <p data-testid="records-totals" className="mb-5 text-sm text-[var(--text-muted)]">
        {totalsLine}
      </p>

      {weeks.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--text-dim)]">Week</span>
          {weeks.map((w) => (
            <Link
              key={w}
              href={href({ week: w })}
              className={`bv-pill ${w === week ? "ring-1 ring-[var(--accent)]" : ""}`}
            >
              <span className="bv-pill-value">{w}</span>
            </Link>
          ))}
          <span className="text-xs text-[var(--text-dim)]">
            {`${rows.length} of ${all.length} games`}
          </span>
        </div>
      )}

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {/* A legend is a note, not a thing: no card around it (Tate 2026-09-16). */}
      <dl className="mb-4 grid grid-cols-1 gap-x-6 gap-y-1 border-t border-[var(--border)] pt-3 text-xs sm:grid-cols-2">
        {LEGEND[view].map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="shrink-0 font-semibold text-[var(--text)]">{k}</dt>
            <dd className="text-[var(--text-muted)]">
              {k === "Gap" && view === "hr" ? `${v}. ${barText}` : v}
            </dd>
          </div>
        ))}
      </dl>

      {rows.length === 0 ? (
        <EmptyLine>{`No games recorded for ${season} yet.`}</EmptyLine>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th className="bv-num">Week</th>
                <th>Matchup</th>
                <th className="bv-num">Full game</th>
                <th className="bv-num">Our number</th>
                {view === "hr" ? (
                  <>
                    <th className="bv-num">Hard Rock</th>
                    <th className="bv-num">Price</th>
                  </>
                ) : (
                  <th className="bv-num">Close</th>
                )}
                <th className="bv-num">Gap</th>
                <th className="bv-num">Actual first half</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const out = view === "hr" ? r.hrOutcome : r.consOutcome;
                return (
                  <tr key={i}>
                    <td className="bv-num text-[var(--text-dim)]">{r.week}</td>
                    <td className="text-[var(--text)]">
                      {r.away}{" "}
                      <span className="text-[var(--text-dim)]">@</span>{" "}
                      {r.home}
                      {r.scoredAfterKickoff && (
                        <span className="bv-badge bv-badge--push ml-2">
                          scored after
                        </span>
                      )}
                    </td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {fmt(r.fullGameTotal)}
                    </td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {fmt(r.bvLine)}
                    </td>
                    {view === "hr" ? (
                      <>
                        <td className="bv-num font-mono text-[var(--text-muted)]">
                          {fmt(r.hrLine)}
                        </td>
                        <td className="bv-num font-mono text-[var(--text-muted)]">
                          {r.hrPrice === null ? "—" : american(r.hrPrice)}
                        </td>
                      </>
                    ) : (
                      <td className="bv-num font-mono text-[var(--text-muted)]">
                        {fmt(r.consLine)}
                      </td>
                    )}
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {gapText(view === "hr" ? r.hrGap : r.consGap)}
                    </td>
                    <td className="bv-num font-mono text-[var(--text-muted)]">
                      {r.firstHalfTotal ?? "—"}
                    </td>
                    <td
                      className="font-semibold"
                      style={{
                        color: labelOf(RESULT_COLOR, out, "var(--text-dim)"),
                      }}
                    >
                      {resultText(r, view)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
