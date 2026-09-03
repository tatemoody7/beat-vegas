"use client";

import { useState } from "react";
import { bookLabel } from "@/lib/books";
import type { EdgeTier } from "@/lib/edge";
import { american, fmt, signed } from "@/lib/format";
import { GAP_BASIS_LABEL, strongestRed, type HomeGame } from "@/lib/homeBoard";
import type { MarketMovement } from "@/lib/movement";
import {
  factorTint,
  groupFactorBoard,
  type BoardFactor,
  type SplitLeg,
  type TeamForm,
  type TeamSplit,
} from "@/lib/score";
import {
  BET_GAP_PTS,
  CONFIDENCE_LABEL,
  STRONG_GAP_PTS,
  WATCH_GAP_PTS,
} from "@/lib/verdict";
import LogPickButton from "@/app/components/LogPickButton";
import MovementChart from "@/app/components/MovementChart";

// One game on the home board: a scannable collapsed row (score, tier, the two
// numbers, what to do) that expands into everything behind it — Lines, Model,
// Why, News. Cyan is the brand accent; green/red only ever carry an under/over
// reading on a factor row.

const TIER_STYLE: Record<EdgeTier, { box: string; sub: string }> = {
  BET: {
    box: "border-transparent bg-[var(--accent-strong)] text-[#04121f]",
    sub: "1 unit, first-half under",
  },
  EDGE: {
    box: "border-[var(--accent-strong)] text-[var(--accent)]",
    sub: "something is there, not yet a bet",
  },
  PASS: {
    box: "border-[var(--border)] text-[var(--text-dim)]",
    sub: "nothing to act on",
  },
};

function bandLabel(gap: number | null): string {
  if (gap === null) return "no gap to measure";
  if (gap >= STRONG_GAP_PTS) return "top ~10% of a season's gaps";
  if (gap >= BET_GAP_PTS) return "top ~20% — the bettable band";
  if (gap >= WATCH_GAP_PTS) return "a small lean, below the band";
  if (gap > 0) return "line sits about on our number";
  return "line sits below our number — leans over";
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-[var(--border-soft)] px-4 py-3">
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
            <th title="The first first-half total this book posted.">Open</th>
            <th title="The most recent first-half total captured.">Now</th>
            <th title="How far the number has moved since it opened. Down is good for an under bet already placed.">
              Move
            </th>
          </tr>
        </thead>
        <tbody>
          {m.books.map((b) => (
            <tr key={b.book}>
              <td className="text-[var(--text)]">{bookLabel(b.book)}</td>
              <td className="font-mono text-[var(--text-muted)]">
                {fmt(b.open)}
              </td>
              <td className="font-mono text-[var(--text)]">{fmt(b.cur)}</td>
              <td className="font-mono text-[var(--text-muted)]">
                {move(b.open, b.cur)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
            label="Our reference 1H"
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
            {`A reference number worked out from the posted full-game total, not a prediction and not a bet.`}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          <Row
            label="Consensus 1H"
            value={
              <>
                <span className="font-mono text-[var(--text)]">
                  {`${fmt(fh.open)} → ${fmt(fh.cur)}`}
                </span>
                {` (${move(fh.open, fh.cur)}) across ${fh.books.length} book${fh.books.length === 1 ? "" : "s"}`}
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

      <div className="mt-3 border-t border-[var(--border-soft)] pt-2">
        <Row
          label="Full game (context)"
          value={
            fg === null && f.full_game_total == null
              ? "—"
              : `total ${fg === null ? fmt(f.full_game_total) : `${fmt(fg.open)} → ${fmt(fg.cur)} (${move(fg.open, fg.cur)})`} · spread ${spreadText(fg, f.spread)}`
          }
        />
        <p className="mt-1 text-xs text-[var(--text-dim)]">
          {`We never bet the full game — it is here because the first-half number is priced off it.`}
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
    <Section title="Model">
      <div className="space-y-1">
        <Row
          label="Our number"
          value={
            row.bvLine === null ? (
              "no model read this week"
            ) : (
              <>
                <span className="font-mono text-[var(--text)]">
                  {fmt(row.bvLine)}
                </span>
                {row.bvLo !== null && row.bvHi !== null
                  ? ` (range ${fmt(row.bvLo, 0)}–${fmt(row.bvHi, 0)})`
                  : ""}
                {row.bvAdjust !== null && row.bvAdjust !== 0
                  ? ` · includes a manual ${signed(row.bvAdjust, 1)}${row.bvAdjustReason ? ` (${row.bvAdjustReason})` : ""}`
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
                {` ${g.gapBasis ? GAP_BASIS_LABEL[g.gapBasis] : ""} — ${bandLabel(g.gap)}`}
              </>
            )
          }
        />
        <Row label="Kill number" value={edge.kill.text} />
        <Row
          label="What makes it wrong"
          value={
            red ??
            "Nothing on the factor board argues against the under right now — which is itself a reason to stay humble: a single first half is close to a coin flip."
          }
        />
      </div>
      {edge.verdict.flags.length > 0 && (
        <ul className="mt-2 space-y-1">
          {edge.verdict.flags.map((fl, i) => (
            <li
              key={i}
              className="rounded-md border border-amber-700/60 bg-amber-950/40 px-2 py-1 text-xs text-amber-300"
            >
              {`⚠ ${fl}`}
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
        <span
          className="bv-fac-badge bv-fac-badge-amber"
          title="Tracks more first-half scoring on the estimated line; unproven against real lines."
        >
          ⚠ unproven
        </span>
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
  const src = t.source === "prior_season" ? " (last season)" : "";
  return `${pf} scored · ${pa || "—"} allowed${src}`;
}

function legText(leg: SplitLeg | undefined): string {
  if (!leg) return "—";
  return `${fmt(leg.pf)} scored / ${fmt(leg.pa)} allowed in ${leg.n}`;
}

function splitText(s: TeamSplit | null | undefined): string {
  if (!s) return "—";
  const home = s.at_home ?? s.home;
  const away = s.on_road ?? s.away;
  if (!home && !away) return "—";
  return `at home ${legText(home)} · on the road ${legText(away)}`;
}

function WhySection({ g }: { g: HomeGame }) {
  const f = g.row.factors;
  const groups = groupFactorBoard(f.factor_board);
  // Each piece only appears when the context job actually wrote it, so the row
  // reads as prose instead of a line of dashes.
  const bits: string[] = [];
  if (f.home_rest_days != null || f.away_rest_days != null) {
    bits.push(
      `rest ${fmt(f.home_rest_days, 0)} days at home vs ${fmt(f.away_rest_days, 0)} for the visitor`,
    );
  }
  if (f.away_travel_dist != null) {
    bits.push(`visitor travelled ${Math.round(f.away_travel_dist)} miles`);
  }
  if (f.away_tz_shift != null && f.away_tz_shift !== 0) {
    bits.push(`time-zone shift ${signed(f.away_tz_shift, 0)} hours`);
  }
  if (f.kickoff_local_hour != null) {
    bits.push(`local kickoff hour ${fmt(f.kickoff_local_hour, 0)}`);
  }
  const restTravel = bits.length > 0 ? bits.join(" · ") : "—";

  return (
    <Section title="Why">
      {groups.length > 0 ? (
        <div className="mb-3">
          {groups.map((grp) => (
            <div key={grp.tier}>
              <div className="bv-fac-tier">{grp.title}</div>
              {grp.factors.map((fac) => (
                <FactorRow key={fac.key} f={fac} />
              ))}
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-3 text-xs text-[var(--text-dim)]">
          {`No factor board on this card yet — it lands when the week is scored.`}
        </p>
      )}
      <div className="space-y-1">
        <Row
          label={`Last 3 1H · ${g.row.away}`}
          value={formText(f.form_away)}
        />
        <Row
          label={`Last 3 1H · ${g.row.home}`}
          value={formText(f.form_home)}
        />
        <Row
          label={`1H splits · ${g.row.away}`}
          value={splitText(f.split_away)}
        />
        <Row
          label={`1H splits · ${g.row.home}`}
          value={splitText(f.split_home)}
        />
        <Row label="Rest & travel" value={restTravel} />
      </div>
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        {`These explain the rating; none of them move it.`}
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
                  ? "var(--over-lean)"
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
          <p className="text-xs text-[var(--text-dim)]">No news.</p>
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
    <Section title="News">
      {qbOut && (
        <p className="mb-2 rounded-md border border-amber-700/60 bg-amber-950/40 px-2 py-1 text-xs text-amber-300">
          {`⚠ QB OUT (live Rotowire, unofficial): ${f.qb_out_detail ?? "a starting quarterback is listed out"}. Our number does not know this.`}
        </p>
      )}
      {p === null ? (
        <p className="text-xs text-[var(--text-dim)]">
          {`No injury or news pull for this game yet (runs Tuesday and Friday mornings). Check the starters yourself before any real bet.`}
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
            {`Unofficial — Rotowire injuries and ESPN headlines${at ? `, pulled ${at} ET` : ""}.`}
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
  const tier = TIER_STYLE[edge.tier];
  const hr =
    check?.hrLine == null
      ? "no HR line"
      : `u${fmt(check.hrLine)}${check.hrUnderPrice == null ? "" : ` ${american(check.hrUnderPrice)}`}`;
  const line = row.curLine ?? row.factors.line ?? null;

  return (
    <div
      className={`bv-card overflow-hidden ${edge.tier === "PASS" ? "opacity-70" : ""}`}
    >
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-start gap-4 p-4 text-left"
      >
        <span
          className="w-12 shrink-0 font-mono text-3xl font-bold leading-none tabular-nums text-[var(--text)]"
          title="Edge score, 0–100: how good this spot looks once the gap, Hard Rock's price and the flags are all counted. It ranks the board; it never overrides the BET rules."
        >
          {edge.score}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span
              className={`rounded-md border px-2 py-0.5 text-xs font-bold tracking-wide ${tier.box}`}
              title={tier.sub}
            >
              {edge.tier}
            </span>
            <span className="text-base font-semibold text-[var(--text)]">
              {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
              {row.home}
            </span>
            <span className="text-xs text-[var(--text-dim)]">
              {g.kickoff ?? "kickoff TBD"}
            </span>
            {g.picked && (
              <span className="rounded-md border border-[var(--accent-strong)] px-1.5 text-xs text-[var(--accent)]">
                logged
              </span>
            )}
          </span>
          <span className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-[var(--text-muted)]">
            <span title="Hard Rock's first-half total and under price — the only book you can bet from Florida.">
              {`Hard Rock ${hr}`}
            </span>
            <span title="The model's own predicted first-half total. It never looks at the Vegas line.">
              {`ours ${fmt(row.bvLine)}`}
            </span>
            <span
              title={`The line minus our number, measured against the number you can actually bet when there is one. ${BET_GAP_PTS}+ is the bettable band.`}
            >
              {g.gap === null
                ? "gap —"
                : `gap ${signed(g.gap, 1)} ${g.gapBasis ? GAP_BASIS_LABEL[g.gapBasis] : ""}`}
            </span>
            {check?.hrLine == null && line !== null && (
              <span
                title={
                  row.curLine !== null
                    ? "The market's current first-half total across the books that have posted."
                    : "Our reference first-half number, worked out from the full-game total — no book has posted a first-half line."
                }
              >
                {`${row.curLine !== null ? "market" : "reference"} ${fmt(line)}`}
              </span>
            )}
          </span>
          <span className="mt-2 block text-sm text-[var(--text)]">
            {edge.action}
          </span>
        </span>
        <span aria-hidden className="shrink-0 text-xs text-[var(--text-dim)]">
          {open ? "▲ less" : "▼ more"}
        </span>
      </button>

      {open && (
        <div>
          <LinesSection g={g} />
          <ModelSection g={g} />
          <WhySection g={g} />
          <NewsSection g={g} />
          <div className="border-t border-[var(--border-soft)] px-4 py-3">
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
