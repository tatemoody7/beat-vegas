"use client";

import { useState } from "react";
import { bookLabel } from "@/lib/books";
import { american, fmt, signed } from "@/lib/format";
import { SETTLED_WORD } from "@/lib/grade";
import { strongestRed, type HomeGame } from "@/lib/homeBoard";
import { basisPhrase, blockerTag, TIER_TEXT } from "@/lib/labels";
import type { MarketMovement } from "@/lib/movement";
import {
  factorTint,
  type BoardFactor,
  type SplitLeg,
  type TeamForm,
  type TeamSplit,
} from "@/lib/score";
import {
  BET_GAP_PTS,
  WEEKLY_BET_CAP,
  CONFIDENCE_LABEL,
  STRONG_GAP_PTS,
  WATCH_GAP_PTS,
} from "@/lib/verdict";
import LogPickButton from "@/app/components/LogPickButton";
import MovementChart from "@/app/components/MovementChart";
import ScoreBadge from "@/app/components/ScoreBadge";

// One game on the rolling week board: a scannable collapsed row (the coloured
// score, the matchup, the numbers, what to do) that expands into everything
// behind it — Lines, Our number, What is behind it, Injuries and news. The
// score carries the grade colour (lib/grade.ts); cyan stays chrome.

function bandLabel(gap: number | null): string {
  if (gap === null) return "nothing to measure it against";
  if (gap >= STRONG_GAP_PTS)
    return `${STRONG_GAP_PTS}+ — the biggest gaps of a season`;
  if (gap >= BET_GAP_PTS) return `${BET_GAP_PTS}+ — the band we bet`;
  if (gap >= WATCH_GAP_PTS) return `a small lean, under the ${BET_GAP_PTS} bar`;
  if (gap > 0) return "the line sits about on our number";
  return "the line is below our number, so this leans over";
}

/** One chip on the collapsed row. */
function Tag({
  tone,
  children,
}: {
  tone: "good" | "warn" | "bad" | "push" | "accent" | "plain";
  children: React.ReactNode;
}) {
  const mod = tone === "plain" ? "" : `bv-badge--${tone}`;
  return <span className={`bv-badge ${mod}`}>{children}</span>;
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-[var(--border)] px-4 py-3">
      <h4 className="mb-2 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-dim)]">
        {title}
      </h4>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-2 text-xs">
      <span className="min-w-32 text-[var(--text-dim)]">{label}</span>
      <span className="text-[var(--text-muted)]">{value}</span>
    </div>
  );
}

// --- Lines ------------------------------------------------------------------

function move(open: number | null, cur: number | null): string {
  if (open === null || cur === null) return "—";
  const d = Math.round((cur - open) * 100) / 100;
  return d === 0 ? "no move" : signed(d, 1);
}

// Odds API totals rows carry no spread by design, so fall back to the spread
// stored on the card at scoring time rather than showing two dashes.
function spreadText(
  fg: MarketMovement | null,
  stored: number | null | undefined,
): string {
  if (fg !== null && fg.spreadOpen !== null && fg.spreadCur !== null) {
    return `${fmt(fg.spreadOpen)} → ${fmt(fg.spreadCur)}`;
  }
  const one = fg?.spreadCur ?? stored ?? null;
  return one === null ? "—" : fmt(one);
}

function BookTable({ m }: { m: MarketMovement }) {
  return (
    <div className="bv-table-wrap">
      <table className="bv-table">
        <thead>
          <tr>
            <th>Sportsbook</th>
            <th className="bv-num">Open</th>
            <th className="bv-num">Now</th>
            <th className="bv-num">Move</th>
          </tr>
        </thead>
        <tbody>
          {m.books.map((b) => (
            <tr key={b.book}>
              <td className="text-[var(--text)]">{bookLabel(b.book)}</td>
              <td className="bv-num font-mono text-[var(--text-muted)]">
                {fmt(b.open)}
              </td>
              <td className="bv-num font-mono text-[var(--text)]">
                {fmt(b.cur)}
              </td>
              <td className="bv-num font-mono text-[var(--text-muted)]">
                {move(b.open, b.cur)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-xs text-[var(--text-dim)]">
        {`Open is the first first-half total each book posted. Move is how far it has come since. Down is good for an under you already have.`}
      </p>
    </div>
  );
}

function LinesSection({ g }: { g: HomeGame }) {
  const fh = g.movement?.firstHalf ?? null;
  const fg = g.movement?.fullGame ?? null;
  const f = g.row.factors;
  const share =
    f.fh_share !== null &&
    f.fh_share !== undefined &&
    Number.isFinite(f.fh_share)
      ? `${fmt(f.fh_share * 100)}%`
      : null;

  return (
    <Section title="Lines">
      {fh === null ? (
        <div className="space-y-1">
          <p className="text-xs text-[var(--text-muted)]">
            {`No sportsbook has posted a first-half total for this game yet.`}
          </p>
          <Row
            label="Our reference line"
            value={
              <>
                <span className="font-mono text-[var(--text)]">
                  {fmt(f.line ?? null)}
                </span>
                {share !== null && f.full_game_total != null
                  ? ` — ${share} of the full-game total ${fmt(f.full_game_total)}`
                  : share !== null
                    ? ` — ${share} of the full-game total`
                    : ""}
              </>
            }
          />
          <p className="text-xs text-[var(--text-dim)]">
            {`Worked out from the posted full-game total. Not a prediction and not a bet.`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <Row
            label="Market line"
            value={
              <>
                <span className="font-mono text-[var(--text)]">
                  {`${fmt(fh.open)} → ${fmt(fh.cur)}`}
                </span>
                {` (${move(fh.open, fh.cur)}) — the middle of the ${fh.books.length} book${fh.books.length === 1 ? "" : "s"} that have posted`}
              </>
            }
          />
          <BookTable m={fh} />
          <p className="text-xs text-[var(--text-muted)]">{g.priceLine}</p>
          {g.movement !== null && g.movement.points.length > 1 && (
            <MovementChart
              points={g.movement.points}
              books={g.movement.books}
            />
          )}
        </div>
      )}

      <div className="mt-3 border-t border-[var(--border)] pt-2">
        <Row
          label="Full game"
          value={
            fg === null && f.full_game_total == null
              ? "—"
              : `total ${fg === null ? fmt(f.full_game_total) : `${fmt(fg.open)} → ${fmt(fg.cur)} (${move(fg.open, fg.cur)})`} · spread ${spreadText(fg, f.spread)}`
          }
        />
        <p className="mt-1 text-xs text-[var(--text-dim)]">
          {`We never bet the full game. It is here because the first-half line is priced off it.`}
        </p>
      </div>
    </Section>
  );
}

// --- Model ------------------------------------------------------------------

function ModelSection({ g }: { g: HomeGame }) {
  const { row, edge } = g;
  const red = strongestRed(row.factors.factor_board);
  return (
    <Section title="Our number">
      <div className="space-y-1">
        <Row
          label="Our number"
          value={
            row.bvLine === null ? (
              "no model number yet"
            ) : (
              <>
                <span className="font-mono text-[var(--text)]">
                  {fmt(row.bvLine)}
                </span>
                {row.bvLo !== null && row.bvHi !== null
                  ? ` (range ${fmt(row.bvLo, 0)}–${fmt(row.bvHi, 0)})`
                  : ""}
                {row.bvAdjust !== null && row.bvAdjust !== 0
                  ? ` · includes a manual ${signed(row.bvAdjust, 1)} nudge${row.bvAdjustReason ? ` (${row.bvAdjustReason})` : ""}`
                  : ""}
              </>
            )
          }
        />
        <Row
          label="How sure"
          value={CONFIDENCE_LABEL[edge.verdict.confidence]}
        />
        <Row
          label="Gap"
          value={
            g.gap === null ? (
              "—"
            ) : (
              <>
                <span className="font-mono text-[var(--text)]">
                  {signed(g.gap, 1)}
                </span>
                {` ${basisPhrase(g.gapBasis, g.basisBooks)} — ${bandLabel(g.gap)}`}
              </>
            )
          }
        />
        <Row label="Stops being a bet at" value={edge.kill.text} />
        <Row
          label="What argues against it"
          value={red ?? "Nothing here argues against the under."}
        />
      </div>
      {edge.verdict.flags.length > 0 && (
        <ul className="mt-2 space-y-1">
          {edge.verdict.flags.map((fl, i) => (
            <li
              key={i}
              className="rounded-[var(--r-sm)] border border-[var(--warn-border)] bg-[var(--warn-bg)] px-2 py-1 text-xs text-[var(--warn)]"
            >
              {fl}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// --- Why --------------------------------------------------------------------

function FactorRow({ f }: { f: BoardFactor }) {
  const tint = factorTint(f);
  return (
    <div className="bv-fac-row" style={{ background: tint.bg }}>
      <span className="bv-fac-text">
        {f.sentence || `${f.label} — ${f.value}`}
      </span>
      {f.hypothesis && (
        <span className="bv-fac-badge bv-fac-badge-amber">unproven</span>
      )}
    </div>
  );
}

function formText(t: TeamForm | null | undefined): string {
  if (!t || !Array.isArray(t.pf) || t.pf.length === 0) return "—";
  const last = <T,>(xs: T[]) => xs.slice(-3);
  const pf = last(t.pf)
    .map((v) => fmt(v, 0))
    .join(", ");
  const pa = last(t.pa ?? [])
    .map((v) => fmt(v, 0))
    .join(", ");
  const src = t.source === "prior_season" ? " (last season's games)" : "";
  return `${pf} scored · ${pa || "—"} allowed${src}`;
}

function legText(leg: SplitLeg | undefined): string {
  if (!leg) return "—";
  return `${fmt(leg.pf)} scored, ${fmt(leg.pa)} allowed over ${leg.n} game${leg.n === 1 ? "" : "s"}`;
}

function splitText(s: TeamSplit | null | undefined): string {
  if (!s) return "—";
  const home = s.at_home ?? s.home;
  const away = s.on_road ?? s.away;
  if (!home && !away) return "—";
  return `at home ${legText(home)} · away ${legText(away)}`;
}

function WhySection({ g }: { g: HomeGame }) {
  const f = g.row.factors;
  const factors = (f.factor_board ?? []).filter((x) => x && x.key);
  const anyUnproven = factors.some((x) => x.hypothesis);
  // Each piece only appears when the context job actually wrote it, so the row
  // reads as prose instead of a line of dashes.
  const bits: string[] = [];
  if (f.home_rest_days != null || f.away_rest_days != null) {
    bits.push(
      `${g.row.home} had ${fmt(f.home_rest_days, 0)} days off, ${g.row.away} had ${fmt(f.away_rest_days, 0)}`,
    );
  }
  if (f.away_travel_dist != null) {
    bits.push(
      `${g.row.away} travelled ${Math.round(f.away_travel_dist)} miles`,
    );
  }
  if (f.away_tz_shift != null && f.away_tz_shift !== 0) {
    bits.push(
      `${Math.abs(f.away_tz_shift)} hour${Math.abs(f.away_tz_shift) === 1 ? "" : "s"} of time change`,
    );
  }
  if (f.kickoff_local_hour != null) {
    const h = Math.round(f.kickoff_local_hour);
    const local =
      h === 12
        ? "noon"
        : h === 0
          ? "midnight"
          : h > 12
            ? `${h - 12}pm`
            : `${h}am`;
    bits.push(`${local} local kickoff`);
  }
  const restTravel = bits.length > 0 ? bits.join(" · ") : "—";

  return (
    <Section title="What is behind it">
      {factors.length > 0 ? (
        <div className="mb-3">
          {factors.map((fac) => (
            <FactorRow key={fac.key} f={fac} />
          ))}
          {anyUnproven && (
            <p className="mt-1 text-xs text-[var(--text-dim)]">
              {`Rows marked unproven have not been checked against real lines yet.`}
            </p>
          )}
        </div>
      ) : (
        <p className="mb-3 text-xs text-[var(--text-dim)]">
          {`Nothing here yet. It fills in when the week is scored on Sunday.`}
        </p>
      )}
      <div className="space-y-1">
        <Row
          label={`Last 3 first halves · ${g.row.away}`}
          value={formText(f.form_away)}
        />
        <Row
          label={`Last 3 first halves · ${g.row.home}`}
          value={formText(f.form_home)}
        />
        <Row
          label={`Home and away · ${g.row.away}`}
          value={splitText(f.split_away)}
        />
        <Row
          label={`Home and away · ${g.row.home}`}
          value={splitText(f.split_home)}
        />
        <Row label="Rest and travel" value={restTravel} />
      </div>
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        {`These explain the score. None of them change it.`}
      </p>
    </Section>
  );
}

// --- News -------------------------------------------------------------------

// An injury string is "POS Name — Status". Only an actual absence warrants the
// alert color; available players stay neutral.
const ALERT_STATUS =
  /\b(out|doubtful|questionable|suspended|injured reserve|ir)\b/i;

function TeamNews({
  team,
  news,
  injuries,
}: {
  team: string | null;
  news: string[];
  injuries: string[];
}) {
  return (
    <div className="flex-1">
      <div className="mb-1 text-xs font-semibold text-[var(--text)]">
        {team}
      </div>
      {injuries.length > 0 && (
        <ul className="mb-1.5 space-y-0.5">
          {injuries.map((i, k) => (
            <li
              key={k}
              className="text-xs"
              style={{
                color: ALERT_STATUS.test(i)
                  ? "var(--warn)"
                  : "var(--text-muted)",
              }}
            >
              {i}
            </li>
          ))}
        </ul>
      )}
      {news.length > 0 ? (
        <ul className="space-y-0.5">
          {news.map((n, k) => (
            <li key={k} className="text-xs text-[var(--text-muted)]">
              {`• ${n}`}
            </li>
          ))}
        </ul>
      ) : (
        injuries.length === 0 && (
          <p className="text-xs text-[var(--text-dim)]">Nothing reported.</p>
        )
      )}
    </div>
  );
}

function pulledAt(s: string | null): string | null {
  if (!s) return null;
  const d = new Date(`${s.replace(" ", "T")}Z`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleString("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function NewsSection({ g }: { g: HomeGame }) {
  const p = g.preview;
  const f = g.row.factors;
  const qbOut = Boolean(f.qb_out_home || f.qb_out_away);
  const at = pulledAt(p?.updatedAt ?? null);
  return (
    <Section title="Injuries and news">
      {qbOut && (
        <p className="mb-2 rounded-[var(--r-sm)] border border-[var(--warn-border)] bg-[var(--warn-bg)] px-2 py-1 text-xs text-[var(--warn)]">
          {`Starting QB out: ${f.qb_out_detail ?? "a starting quarterback is listed out"}. Unofficial, from Rotowire. Our number does not know about it.`}
        </p>
      )}
      {p === null ? (
        <p className="text-xs text-[var(--text-dim)]">
          {`No injuries or news pulled for this game yet. Check the starting lineups yourself before any real bet.`}
        </p>
      ) : (
        <>
          <div className="flex flex-col gap-3 sm:flex-row">
            <TeamNews
              team={p.away}
              news={p.awayNews}
              injuries={p.awayInjuries}
            />
            <TeamNews
              team={p.home}
              news={p.homeNews}
              injuries={p.homeInjuries}
            />
          </div>
          <p className="mt-2 text-xs text-[var(--text-dim)]">
            {`Unofficial: Rotowire injuries and ESPN headlines${at ? `, pulled ${at} ET` : ""}. Check the lineups yourself.`}
          </p>
        </>
      )}
    </Section>
  );
}

// --- the card ---------------------------------------------------------------

export default function GameCard({ g }: { g: HomeGame }) {
  const [open, setOpen] = useState(false);
  const { row, edge, check } = g;
  const hr =
    check?.hrLine == null
      ? "no line yet"
      : `u${fmt(check.hrLine)}${check.hrUnderPrice == null ? "" : ` ${american(check.hrUnderPrice)}`}`;
  const line = row.curLine ?? row.factors.line ?? null;
  const basis = g.gapBasis;
  const tag =
    edge.tier === "EDGE"
      ? blockerTag(edge.blocker, {
          hrLine: check?.hrLine ?? null,
          hrPrice: check?.hrUnderPrice ?? null,
          marketLine: row.curLine,
          killLine: edge.kill.line,
          killPrice: edge.kill.price,
        })
      : null;
  const resultLine =
    g.settled !== null && row.firstHalfTotal !== null
      ? `${SETTLED_WORD[g.settled][0].toUpperCase()}${SETTLED_WORD[g.settled].slice(1)} · first half ${fmt(row.firstHalfTotal, 0)}, line ${fmt(check?.hrLine ?? line)}`
      : null;

  return (
    <div
      id={`game-${row.gameId}`}
      data-interactive="true"
      className={`bv-card scroll-mt-4 overflow-hidden ${edge.tier === "PASS" && g.settled === null ? "opacity-85" : ""}`}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full flex-col items-stretch p-4 text-left"
      >
        <span className="flex items-start gap-3">
          <ScoreBadge
            score={edge.score}
            settled={g.settled}
            label={g.settled === null ? TIER_TEXT[edge.tier] : undefined}
          />
          <span className="min-w-0 flex-1">
            <span className="block text-base font-semibold leading-snug text-[var(--text)]">
              {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
              {row.home}
            </span>
            <span className="mt-0.5 block text-xs text-[var(--text-dim)]">
              {g.kickoff ?? "kickoff time TBD"}
            </span>
          </span>
          <span
            aria-hidden
            className="shrink-0 pt-1 text-xs text-[var(--text-dim)]"
          >
            {open ? "▲ less" : "▼ more"}
          </span>
        </span>
        {(g.picked ||
          g.overCap ||
          g.earlySeason ||
          tag !== null ||
          (g.kickedOff && g.settled === null)) && (
          <span className="mt-2 flex flex-wrap gap-1.5">
            {g.picked && <Tag tone="accent">bet logged</Tag>}
            {g.overCap && (
              <Tag tone="push">{`past the ${WEEKLY_BET_CAP}-bet cap · paper only`}</Tag>
            )}
            {g.kickedOff && g.settled === null && (
              <Tag tone="push">already kicked off</Tag>
            )}
            {g.earlySeason && <Tag tone="warn">early season</Tag>}
            {tag !== null && (
              <span className="bv-badge bv-badge--warn bv-badge--wrap">
                {tag}
              </span>
            )}
          </span>
        )}
        <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-[var(--text-muted)]">
          <span>{`Hard Rock ${hr}`}</span>
          <span>{`our number ${fmt(row.bvLine)}`}</span>
          <span>
            {g.gap === null
              ? "gap —"
              : `gap ${signed(g.gap, 1)} ${basisPhrase(basis, g.basisBooks)}`}
          </span>
          {check?.hrLine == null && line !== null && (
            <span>
              {`${row.curLine !== null ? "market line" : "our reference line"} ${fmt(line)}`}
            </span>
          )}
        </span>
        <span className="mt-2 block text-sm text-[var(--text)]">
          {resultLine ?? edge.action}
        </span>
      </button>

      {open && (
        <div>
          <LinesSection g={g} />
          <ModelSection g={g} />
          <WhySection g={g} />
          <NewsSection g={g} />
          <div className="border-t border-[var(--border)] px-4 py-3">
            <LogPickButton
              prefill={{
                gameId: row.gameId,
                away: row.away,
                home: row.home,
                line: check?.hrLine ?? line,
                price: check?.hrUnderPrice ?? null,
                verdict: edge.verdict.verdict,
                reason: edge.verdict.reason,
                gap: edge.verdict.hrGap,
                ev: check?.ev ?? null,
                hrLine: check?.hrLine ?? null,
                fairUnder: check?.marketFairUnder ?? null,
              }}
              picked={g.picked}
              kickedOff={g.kickedOff}
            />
          </div>
        </div>
      )}
    </div>
  );
}
