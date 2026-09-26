"use client";

import React, { useState } from "react";
import {
  groupByWeek,
  hoursBeforeKickoff,
  ledgerSummary,
  rowsFor,
  withRunningUnits,
  type LedgerRow,
  type LedgerView,
  type RunningRow,
} from "@/lib/betLedger";
import { displayLineValue } from "@/lib/clvDirection";
import { etStamp } from "@/lib/et";
import { american, signed, unitColor } from "@/lib/format";
import {
  labelOf,
  MARKET_TEXT,
  PROVENANCE_TEXT,
  RESULT_COLOR,
  RESULT_PENDING,
  RESULT_TEXT,
} from "@/lib/labels";
import { loggedAs } from "@/lib/loggedAs";
import { isOffPolicy } from "@/lib/pickRules";
import { EmptyLine } from "@/app/components/Section";

// Every bet we have placed, at the top of Track record (Tate 2026-09-26): the
// real-money ledger first with the paper ledger one click away, grouped by
// week newest first, each week carrying its own record, each graded row
// washed in its outcome colour, a running units column so the curve can be
// read off the table, and a proof row under each bet with the posted time,
// our number, the closing line and the note -- frozen when the pick was
// logged. Nothing here is a tooltip: a phone never shows one.

const VIEW_LABEL: Record<LedgerView, string> = {
  real: "My money",
  paper: "The rule, on paper",
  all: "Both ledgers",
};

const pct = (v: number) => `${(100 * v).toFixed(0)}%`;
const num = (n: number | null, dp = 2) => (n === null ? "—" : signed(n, dp));
const et = (iso: string | null) =>
  iso === null ? null : `${etStamp(new Date(iso))} ET`;

function scoreText(r: LedgerRow): string {
  if (!r.graded) return "—";
  if (r.awayFh !== null && r.homeFh !== null) {
    return `${r.awayFh}–${r.homeFh} · ${r.actualTotal ?? r.awayFh + r.homeFh}`;
  }
  return r.actualTotal === null ? "—" : `${r.actualTotal}`;
}

function rowClass(r: LedgerRow): string {
  if (!r.graded) return "align-top";
  if (r.result === "under") return "align-top bv-row--won";
  if (r.result === "over") return "align-top bv-row--lost";
  if (r.result === "push") return "align-top bv-row--push";
  return "align-top";
}

function beforeKickoff(r: LedgerRow): string | null {
  const h = hoursBeforeKickoff(r);
  if (h === null) return null;
  if (h < 0) return `${-h} h after kickoff`;
  if (h >= 48) return `${Math.floor(h / 24)} d ${h % 24} h before kickoff`;
  return `${h} h before kickoff`;
}

export default function BetLedger({
  rows,
  season,
}: {
  rows: LedgerRow[];
  season: number;
}) {
  const realCount = rows.filter((r) => !r.isPaper).length;
  const paperCount = rows.length - realCount;
  const [view, setView] = useState<LedgerView>(realCount > 0 ? "real" : "all");
  const [open, setOpen] = useState<number | null>(null);

  const shown = rowsFor(rows, view);
  const summary = ledgerSummary(shown);
  const groups = groupByWeek(withRunningUnits(shown));
  const rec = summary.record;
  const interval =
    rec && rec.hitLo !== null && rec.hitHi !== null
      ? `plausibly ${pct(rec.hitLo)}–${pct(rec.hitHi)}`
      : "nothing decided yet";

  const VIEWS: { id: LedgerView; label: string; n: number }[] = [
    { id: "real", label: "My bets", n: realCount },
    { id: "paper", label: "Paper", n: paperCount },
    { id: "all", label: "All", n: rows.length },
  ];

  return (
    <section aria-label="Every bet" className="mb-10">
      <div className="bv-card p-5">
        <div className="grid grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-3">
          <div>
            <span className="bv-stat-label">{VIEW_LABEL[view]}</span>
            {rec === null ? (
              <EmptyLine className="mt-2">
                {summary.bets === 0
                  ? `No bets logged in ${season} yet.`
                  : `${summary.bets} logged, none graded yet.`}
              </EmptyLine>
            ) : (
              <>
                <p className="mt-2 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
                  {rec.hit}
                </p>
                <p className="mt-2.5 font-mono text-sm text-[var(--text-muted)]">
                  {`${rec.record} · ${summary.bets} ${summary.bets === 1 ? "bet" : "bets"} · `}
                  <span style={{ color: unitColor(rec.units) }}>
                    {`${rec.units}u`}
                  </span>
                  {` · ROI ${rec.roi}`}
                </p>
                <p className="mt-1 text-xs text-[var(--text-dim)]">
                  {interval}
                </p>
              </>
            )}
          </div>
          <div>
            <span className="bv-stat-label">Line value</span>
            <p className="mt-2 font-[family-name:var(--font-display)] text-5xl font-extrabold leading-none tabular-nums text-[var(--text)]">
              {rec?.clv ?? "—"}
            </p>
            <p className="mt-2.5 text-sm text-[var(--text-muted)]">
              points the market came toward us
            </p>
            <p className="mt-1 text-xs text-[var(--text-dim)]">
              {summary.closes === 0
                ? "no closes captured yet"
                : `${pct(summary.movedOurWay / summary.closes)} of ${summary.closes} lines moved our way`}
            </p>
          </div>
          <div>
            <span className="bv-stat-label">Every bet, as logged</span>
            <p className="mt-2 text-sm text-[var(--text-muted)]">
              Each row was posted before kickoff with Hard Rock’s line and
              price. Open a row for our number at the time, the closing line and
              when it was posted.
            </p>
            <a
              href={`/api/bets?season=${season}`}
              className="bv-btn bv-btn--ghost mt-3 inline-block"
            >
              Download every bet (CSV)
            </a>
          </div>
        </div>
      </div>

      <div
        role="tablist"
        aria-label="Which bets to show"
        className="mt-5 flex flex-wrap gap-2"
      >
        {VIEWS.map((v) => (
          <button
            key={v.id}
            type="button"
            role="tab"
            aria-selected={view === v.id}
            onClick={() => {
              setView(v.id);
              setOpen(null);
            }}
            className="bv-chip"
          >
            {`${v.label} ${v.n}`}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <EmptyLine className="mt-3">
          {view === "real"
            ? "No real-money bets logged yet."
            : "No paper picks logged yet."}
        </EmptyLine>
      ) : (
        groups.map((g) => (
          <div key={g.week ?? "none"}>
            <h3 className="bv-day-head">
              {`Week ${g.week ?? "?"} · ${g.rows.length} ${g.rows.length === 1 ? "bet" : "bets"}`}
              {g.record ? (
                <>
                  {` · ${g.record.record} · `}
                  <span style={{ color: unitColor(g.record.units) }}>
                    {`${g.record.units}u`}
                  </span>
                </>
              ) : (
                " · pending"
              )}
              {g.record && g.pending > 0 ? ` · ${g.pending} pending` : ""}
            </h3>
            <div className="bv-table-wrap">
              <table
                className="bv-table"
                aria-label={`Week ${g.week ?? "?"} bets`}
              >
                <thead>
                  <tr>
                    <th>Placed</th>
                    <th>Matchup</th>
                    <th className="bv-num">Bet</th>
                    <th className="bv-num">Price</th>
                    <th className="bv-num">Stake</th>
                    <th className="bv-num">1H score</th>
                    <th>Result</th>
                    <th className="bv-num">Units</th>
                    <th className="bv-num">Running</th>
                    <th className="bv-num">Line value</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {g.rows.map((p) => (
                    <LedgerRowView
                      key={p.id}
                      p={p}
                      open={open === p.id}
                      toggle={() => setOpen(open === p.id ? null : p.id)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
      <p className="mt-3 text-xs text-[var(--text-dim)]">
        Frozen when the pick was logged. Running is the ledger’s units after
        that bet; a line value of +1.00 means the market came a point toward us
        by the close.
      </p>
    </section>
  );
}

function LedgerRowView({
  p,
  open,
  toggle,
}: {
  p: RunningRow;
  open: boolean;
  toggle: () => void;
}) {
  const posted = et(p.placedAt);
  const lead = beforeKickoff(p);
  return (
    <>
      <tr className={rowClass(p)}>
        <td className="whitespace-nowrap text-[var(--text-muted)]">
          {p.placedAt ? etStamp(new Date(p.placedAt)) : "—"}
        </td>
        <td className="text-[var(--text)]">
          {/* The names stay on one line; a badge may wrap under them. A
              fully unwrappable cell pushed the week's table past its box at
              1440 and hid the details toggle (seen on production, 09-26). */}
          <span className="whitespace-nowrap">
            {p.away} <span className="text-[var(--text-dim)]">@</span> {p.home}
          </span>
          {p.market === "full" && (
            <span className="bv-badge ml-1">
              {labelOf(MARKET_TEXT, p.market, "Full game")}
            </span>
          )}
          {p.isPaper && (
            <span className="bv-badge bv-badge--warn ml-1">paper</span>
          )}
          {p.isBonus && (
            <span className="bv-badge ml-1">bonus — a loss costs nothing</span>
          )}
          {isOffPolicy(p) && (
            <span className="bv-badge bv-badge--warn ml-1">
              against the verdict
            </span>
          )}
        </td>
        <td className="bv-num whitespace-nowrap text-[var(--text-muted)]">
          {p.line !== null ? `under ${p.line}` : "—"}
        </td>
        <td className="bv-num font-mono text-[var(--text-muted)]">
          {p.price === null ? "—" : american(p.price)}
        </td>
        <td className="bv-num font-mono text-[var(--text-muted)]">
          {p.stake === null ? "—" : `${p.stake}u`}
        </td>
        <td className="bv-num whitespace-nowrap font-mono text-[var(--text-muted)]">
          {scoreText(p)}
        </td>
        <td>
          <span
            style={{
              color: p.graded
                ? labelOf(RESULT_COLOR, p.result, "var(--text-dim)")
                : "var(--text-dim)",
            }}
          >
            {p.graded
              ? labelOf(RESULT_TEXT, p.result, RESULT_PENDING)
              : RESULT_PENDING}
          </span>
        </td>
        <td
          className="bv-num font-mono"
          style={{
            color:
              p.units === null
                ? "var(--text-dim)"
                : p.units >= 0
                  ? "var(--good)"
                  : "var(--bad)",
          }}
        >
          {num(p.units)}
        </td>
        <td
          className="bv-num font-mono"
          style={{
            color:
              p.runningUnits === null
                ? "var(--text-dim)"
                : p.runningUnits >= 0
                  ? "var(--good)"
                  : "var(--bad)",
          }}
        >
          {num(p.runningUnits)}
        </td>
        <td className="bv-num font-mono text-[var(--text-muted)]">
          {num(displayLineValue(p.clv))}
        </td>
        <td className="whitespace-nowrap">
          <button
            type="button"
            onClick={(e) => {
              // Bring the row's left edge back into view before the proof
              // opens under it (the wrap scrolls sideways on a phone).
              e.currentTarget
                .closest(".bv-table-wrap")
                ?.scrollTo({ left: 0, behavior: "smooth" });
              toggle();
            }}
            aria-expanded={open}
            aria-controls={`bet-detail-${p.id}`}
            className="text-xs text-[var(--text-dim)] hover:text-[var(--accent)]"
          >
            {open ? "hide" : "details"}
          </button>
        </td>
      </tr>
      {open && (
        <tr id={`bet-detail-${p.id}`} className="bg-[var(--surface-2)]">
          <td colSpan={11} className="px-3 py-3">
            {/* The table scrolls sideways on a phone and the toggle scrolls
                it back to the left edge, so the proof always fits the screen
                (a sticky panel inside a table cell pins to the viewport in
                Chrome, not to the table -- measured, not assumed). */}
            <dl
              className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm"
              style={{ maxWidth: "calc(100vw - 4rem)" }}
            >
              <dt className="text-[var(--text-dim)]">Our number then</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {p.modelLine === null ? "—" : p.modelLine.toFixed(2)}
              </dd>
              <dt className="text-[var(--text-dim)]">Why it was logged</dt>
              <dd className="text-[var(--text-muted)]">{loggedAs(p)}</dd>
              <dt className="text-[var(--text-dim)]">Posted</dt>
              <dd className="text-[var(--text-muted)]">
                {posted ?? "—"}
                {lead ? ` · ${lead}` : ""}
              </dd>
              <dt className="text-[var(--text-dim)]">Price</dt>
              <dd className="text-[var(--text-muted)]">
                {p.book === null ? "no book recorded" : p.book}
                {p.priceProvenance
                  ? ` · ${labelOf(PROVENANCE_TEXT, p.priceProvenance, "price not verified")}`
                  : ""}
              </dd>
              <dt className="text-[var(--text-dim)]">Closing line</dt>
              <dd className="font-mono text-[var(--text-muted)]">
                {p.closingLine === null
                  ? "—"
                  : `${p.closingLine}${p.closingPrice === null ? "" : ` at ${american(p.closingPrice)}`}${
                      p.closingCapturedAt
                        ? ` · captured ${et(p.closingCapturedAt)}`
                        : ""
                    }`}
              </dd>
              <dt className="text-[var(--text-dim)]">Note</dt>
              <dd className="text-[var(--text-muted)]">{p.note ?? "—"}</dd>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}
