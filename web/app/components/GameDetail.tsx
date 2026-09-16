import Link from "next/link";
import { bookLabel } from "@/lib/books";
import { american, capitalize, fmt, signed } from "@/lib/format";
import type { HomeGame } from "@/lib/homeBoard";
import type { MarketMovement } from "@/lib/movement";
import {
  factorTint,
  type BoardFactor,
  type SplitLeg,
  type TeamForm,
  type TeamSplit,
} from "@/lib/score";
import { WEEKLY_BET_CAP } from "@/lib/verdict";
import LogPickButton from "@/app/components/LogPickButton";
import TeamLogo from "@/app/components/TeamLogo";

// One game, in full. This is where every number the board used to hide behind a
// disclosure now lives: the decision up top (the three numbers, the sentence,
// the log button), then Lines, What is behind it, and Injuries and news. The
// board row is a link to here and carries none of it.
//
// There is no "Our number" section: the decision block already states the
// number (Tate, 2026-09-10). Since 2026-09-16 the decision is the three tiles
// and the sentence alone: the gap bar, the gap caption, the blocker tag and the
// price line each said the same gap a different way, and Tate cut them; the
// tier word left the header and the full-game line left Lines for the same
// reason. Every caption a returning reader does not need is gone too.
//
// Colour is the grade language (globals.css): --good bet, --warn watch,
// --bad pass. Cyan stays chrome — links and buttons only.

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bv-card p-4">
      <h2 className="mb-3 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-dim)]">
        {title}
      </h2>
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
    </div>
  );
}

function LinesSection({ g }: { g: HomeGame }) {
  const fh = g.movement?.firstHalf ?? null;
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
          {/* The per-book time-series chart that sat here is gone (Tate,
              2026-09-13: "scribbles"), and so is the full-game footer
              (2026-09-16); the table is the movement read. */}
        </div>
      )}
    </Section>
  );
}

// --- What is behind it ------------------------------------------------------

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
  const factors: BoardFactor[] = (f.factor_board ?? []).filter(
    (x) => x && x.key,
  );
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
        </div>
      ) : (
        <p className="mb-3 text-xs text-[var(--text-dim)]">
          {`Nothing here yet. It fills in when the week is scored.`}
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
    </Section>
  );
}

// --- Injuries and news ------------------------------------------------------

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
          {`Starting QB out: ${f.qb_out_detail ?? "a starting quarterback is listed out"}. Our number does not know about it.`}
        </p>
      )}
      {p === null ? (
        <p className="text-xs text-[var(--text-dim)]">
          {`No injuries or news pulled for this game yet.`}
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
          {at && (
            <p className="mt-2 text-xs text-[var(--text-dim)]">
              {`Rotowire and ESPN, pulled ${at} ET`}
            </p>
          )}
        </>
      )}
    </Section>
  );
}

// --- the page ---------------------------------------------------------------

/** Tier colour, the same language the board badge speaks. */
function tierTone(g: HomeGame): string {
  if (g.settled !== null) return "var(--push)";
  if (g.edge.tier === "BET") return "var(--good)";
  if (g.edge.tier === "PASS") return "var(--bad)";
  return "var(--warn)";
}

export default function GameDetail({
  g,
  unitUsd,
  backHref,
  authed,
}: {
  g: HomeGame;
  /** The flat stake, read server-side — a client component cannot read it. */
  unitUsd: number;
  backHref: string;
  /** Signed in (or the gate is off): the log-pick form is offered. */
  authed: boolean;
}) {
  const { row, edge, check } = g;
  const line = check?.hrLine ?? row.curLine ?? row.factors.line ?? null;
  const tone = tierTone(g);
  const played = row.firstHalfTotal !== null;
  const resultLine =
    played && g.settled !== null
      ? `${capitalize(g.settled)} · first half ${fmt(row.firstHalfTotal, 0)}, line ${fmt(g.settledLine)}`
      : played
        ? `Final · first half ${fmt(row.firstHalfTotal, 0)}. No first-half line was posted, so nothing to grade.`
        : null;

  return (
    <div className="space-y-4">
      <div className="sticky top-[var(--header-h)] z-10 -mx-4 border-b border-[var(--border)] bg-[var(--bg)]/95 px-4 py-3 backdrop-blur">
        <Link
          href={backHref}
          className="text-xs text-[var(--accent)] hover:underline"
        >
          ← Back to the board
        </Link>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          {g.boardRank !== null && (
            <span
              className="rounded-[var(--r-sm)] px-2 py-0.5 font-mono text-lg font-semibold"
              style={{ background: tone, color: "var(--badge-ink)" }}
            >
              {`#${g.boardRank}`}
            </span>
          )}
          <h1 className="text-2xl font-semibold text-[var(--text)]">
            <TeamLogo teamId={row.awayTeamId} />
            {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
            <TeamLogo teamId={row.homeTeamId} />
            {row.home}
          </h1>
          <span className="text-sm text-[var(--text-dim)]">
            {g.kickoff ?? "kickoff time TBD"}
          </span>
        </div>
      </div>

      <section className="bv-card p-4">
        <h2 className="mb-3 text-[0.65rem] font-semibold uppercase tracking-[0.08em] text-[var(--text-dim)]">
          The decision
        </h2>

        <div className="mb-4 flex flex-wrap gap-1.5">
          {g.picked && (
            <span className="bv-badge bv-badge--accent">bet logged</span>
          )}
          {g.overCap && (
            <span className="bv-badge bv-badge--push">{`past the ${WEEKLY_BET_CAP}-bet cap · paper only`}</span>
          )}
          {g.capRank !== null && !g.overCap && (
            <span className="bv-badge bv-badge--push">{`cap slot ${g.capRank}`}</span>
          )}
          {g.kickedOff && g.settled === null && (
            <span className="bv-badge bv-badge--push">already kicked off</span>
          )}
          {g.earlySeason && (
            <span className="bv-badge bv-badge--warn">early season</span>
          )}
        </div>

        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Stat
            label="Hard Rock"
            value={
              check?.hrLine == null
                ? "no line yet"
                : `u${fmt(check.hrLine)}${check.hrUnderPrice == null ? "" : ` ${american(check.hrUnderPrice)}`}`
            }
          />
          <Stat
            label="Market"
            value={row.curLine === null ? "—" : `u${fmt(row.curLine)}`}
          />
          <Stat
            label="Our number"
            value={row.bvLine === null ? "—" : fmt(row.bvLine)}
          />
        </div>

        <p
          className={`text-base ${played && g.settled === null ? "text-[var(--text-dim)]" : "text-[var(--text)]"}`}
        >
          {resultLine ?? edge.action}
        </p>

        <div className="mt-4 border-t border-[var(--border)] pt-3">
          <LogPickButton
            authed={authed}
            unitUsd={unitUsd}
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
            }}
            picked={g.picked}
            kickedOff={g.kickedOff}
          />
        </div>
      </section>

      <LinesSection g={g} />
      <WhySection g={g} />
      <NewsSection g={g} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--r-sm)] bg-[var(--bg-2)] px-3 py-2">
      <div className="text-[0.6rem] uppercase tracking-[0.06em] text-[var(--text-dim)]">
        {label}
      </div>
      <div className="font-mono text-lg text-[var(--text)]">{value}</div>
    </div>
  );
}
