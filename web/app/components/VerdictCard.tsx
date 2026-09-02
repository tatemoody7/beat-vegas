import { bookLabel } from "@/lib/books";
import type { PreviewGame } from "@/lib/preview";
import type { ThisWeekGame } from "@/lib/thisWeek";
import { CONFIDENCE_LABEL, type Confidence, type Verdict } from "@/lib/verdict";
import LogPickButton from "@/app/components/LogPickButton";

// Verdict chrome uses the brand accent (cyan) and neutral slate — never green or
// red, which are reserved for under/over OUTCOMES on settled bets.
const VERDICT_STYLE: Record<
  Verdict,
  { bg: string; border: string; text: string }
> = {
  BET: {
    bg: "var(--accent-soft)",
    border: "var(--accent-strong)",
    text: "var(--accent)",
  },
  WATCH: { bg: "rgba(224,164,74,0.10)", border: "#6b4a1f", text: "#e0a44a" },
  PASS: {
    bg: "var(--surface-2)",
    border: "var(--border)",
    text: "var(--text-dim)",
  },
};

const CONF_DOTS: Record<Confidence, number> = {
  high: 3,
  medium: 2,
  low: 1,
  none: 0,
};

function ConfidenceMeter({ c }: { c: Confidence }) {
  const on = CONF_DOTS[c];
  return (
    <span
      className="inline-flex items-center gap-1"
      title="How sure the system is: three dots = a top-10% gap at Hard Rock’s number with the classifier agreeing, at a fair-or-better price; one dot = a small lean or a price-only edge; none = no read."
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="inline-block h-1.5 w-4 rounded-sm"
          style={{ background: i < on ? "var(--accent)" : "var(--border)" }}
        />
      ))}
      <span className="ml-1 text-xs text-[var(--text-muted)]">
        {CONFIDENCE_LABEL[c]}
      </span>
    </span>
  );
}

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

function InjuriesBlock({ p }: { p: PreviewGame | null }) {
  if (!p) {
    return (
      <p className="mt-3 text-xs text-[var(--text-dim)]">
        No injury or news pull for this game yet (runs Tuesday and Friday
        mornings). Check starters yourself before any real bet.
      </p>
    );
  }
  const n = p.homeInjuries.length + p.awayInjuries.length;
  const m = p.homeNews.length + p.awayNews.length;
  const at = pulledAt(p.updatedAt);
  return (
    <details className="mt-3 rounded-md border border-[var(--border-soft)] bg-[var(--bg-2)] px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-[var(--text-muted)]">
        {`Injuries & news · ${n} injur${n === 1 ? "y" : "ies"} · ${m} news item${m === 1 ? "" : "s"}`}
        <span className="ml-2 font-normal text-[var(--text-dim)]">
          {`unofficial (Rotowire / ESPN)${at ? ` · pulled ${at} ET` : ""}`}
        </span>
      </summary>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <TeamNews team={p.away} news={p.awayNews} injuries={p.awayInjuries} />
        <TeamNews team={p.home} news={p.homeNews} injuries={p.homeInjuries} />
      </div>
    </details>
  );
}

function AllBooks({ g }: { g: ThisWeekGame }) {
  const c = g.check;
  if (!c || c.books.length === 0) {
    return (
      <p className="mt-2 text-xs text-[var(--text-dim)]">
        No sportsbook has posted a first-half total yet (swept Friday afternoon
        and Saturday morning).
      </p>
    );
  }
  return (
    <details className="mt-2 rounded-md border border-[var(--border-soft)] bg-[var(--bg-2)] px-3 py-2">
      <summary className="cursor-pointer text-xs font-medium text-[var(--text-muted)]">
        {`All books (${c.books.length}) · best ${c.best?.toFixed(1) ?? "—"} · median ${c.median?.toFixed(1) ?? "—"}`}
        {c.hrLine !== null && c.delta !== null && (
          <span className="ml-2 font-normal text-[var(--text-dim)]">
            {c.delta === 0
              ? "Hard Rock has the best number"
              : `Hard Rock is ${Math.abs(c.delta).toFixed(1)} below the best`}
          </span>
        )}
      </summary>
      <div className="bv-table-wrap mt-2">
        <table className="bv-table">
          <thead>
            <tr>
              <th>Sportsbook</th>
              <th>1H total</th>
              <th title="How far this book sits below the best (highest) total. For an under, higher is better.">
                vs best
              </th>
              <th title="This book’s under price.">Under</th>
            </tr>
          </thead>
          <tbody>
            {c.books.map((b) => {
              const d =
                c.best !== null ? Number((b.line - c.best).toFixed(2)) : null;
              return (
                <tr
                  key={b.book}
                  style={
                    b.isHR
                      ? {
                          background:
                            "color-mix(in srgb, var(--accent) 12%, transparent)",
                        }
                      : undefined
                  }
                >
                  <td className="text-[var(--text)]">
                    {bookLabel(b.book)}
                    {b.isHR ? " ★" : ""}
                    {b.isExchange && (
                      <span
                        className="bv-fac-badge ml-1"
                        title="CFTC-regulated exchange: prices carry almost no vig, so they anchor the market fair price. Legal in Florida but no first-half totals — we never bet here."
                      >
                        no-vig
                      </span>
                    )}
                  </td>
                  <td className="font-mono text-[var(--text)]">
                    {b.line.toFixed(1)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {d === null || d === 0 ? "—" : d.toFixed(1)}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {b.underPrice === null
                      ? "—"
                      : `${b.underPrice > 0 ? "+" : ""}${b.underPrice}`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default function VerdictCard({ g }: { g: ThisWeekGame }) {
  const { row, verdict: v, check } = g;
  const style = VERDICT_STYLE[v.verdict];
  const line = row.curLine ?? row.factors.line ?? null;
  const derived = row.factors.line_kind === "derived_fg";

  return (
    <div
      className="bv-card overflow-hidden"
      style={{ borderColor: style.border }}
    >
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:gap-5">
        {/* Verdict block */}
        <div
          className="flex w-full shrink-0 flex-col items-center justify-center rounded-lg px-3 py-3 text-center sm:w-32"
          style={{ background: style.bg }}
        >
          <span
            className="font-[family-name:var(--font-display)] text-2xl font-extrabold tracking-tight"
            style={{ color: style.text }}
          >
            {v.verdict}
          </span>
          <span className="mt-1 text-[0.65rem] uppercase tracking-wide text-[var(--text-dim)]">
            {v.verdict === "BET"
              ? "1 unit, under"
              : v.verdict === "WATCH"
                ? "not yet"
                : "no bet"}
          </span>
        </div>

        {/* Body */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="text-lg font-semibold text-[var(--text)]">
              {row.away} <span className="text-[var(--text-dim)]">@</span>{" "}
              {row.home}
            </h3>
            <div className="flex items-center gap-3">
              <ConfidenceMeter c={v.confidence} />
              <span className="rounded-md bg-[var(--surface-2)] px-2 py-0.5 text-xs font-medium text-[var(--text-muted)]">
                {`Wk ${row.week}`}
              </span>
            </div>
          </div>

          {/* The numbers that matter, in words */}
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1.5">
            <div
              className="bv-stat"
              title={
                derived
                  ? "Reference first-half number from the full-game total — not a market line."
                  : "The market’s current first-half total (or our estimate when none is posted)."
              }
            >
              <span className="bv-stat-label">
                {row.curLine !== null
                  ? "1H line"
                  : derived
                    ? "Reference 1H"
                    : "Est. 1H line"}
              </span>
              <span className="bv-stat-value">
                {line !== null ? line.toFixed(1) : "—"}
              </span>
            </div>
            {!derived && row.bvLine !== null && (
              <div
                className="bv-stat"
                title="The model’s own predicted first-half total. It never looks at the Vegas line."
              >
                <span className="bv-stat-label">Our number</span>
                <span className="bv-stat-value">{row.bvLine.toFixed(1)}</span>
              </div>
            )}
            <div
              className="bv-stat"
              title="Hard Rock’s posted first-half total and under price — the only book you can bet from Florida."
            >
              <span className="bv-stat-label">Hard Rock</span>
              <span className="bv-stat-value">
                {check?.hrLine != null
                  ? `u${check.hrLine.toFixed(1)}${check.hrUnderPrice != null ? ` ${check.hrUnderPrice > 0 ? "+" : ""}${check.hrUnderPrice}` : ""}`
                  : "not posted"}
              </span>
            </div>
            {v.hrGap !== null && (
              <div
                className="bv-stat"
                title="Hard Rock’s line minus our number — the gap you can actually bet. 1.75+ is the bettable band."
              >
                <span className="bv-stat-label">Gap at Hard Rock</span>
                <span className="bv-stat-value">
                  {`${v.hrGap > 0 ? "+" : ""}${v.hrGap.toFixed(1)}`}
                </span>
              </div>
            )}
            {g.picked && (
              <span className="self-end rounded-md border border-[var(--accent-strong)] px-2 py-0.5 text-xs text-[var(--accent)]">
                logged
              </span>
            )}
          </div>

          <p className="mt-3 text-sm font-medium text-[var(--text)]">
            {v.headline}
          </p>
          <ul className="mt-1.5 space-y-1 text-sm text-[var(--text-muted)]">
            {v.why.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
          {v.flags.length > 0 && (
            <ul className="mt-2 space-y-1">
              {v.flags.map((f, i) => (
                <li
                  key={i}
                  className="rounded-md border border-amber-700/60 bg-amber-950/40 px-2 py-1 text-xs text-amber-300"
                >
                  {`⚠ ${f}`}
                </li>
              ))}
            </ul>
          )}

          <InjuriesBlock p={g.preview} />
          <AllBooks g={g} />

          {/* Every un-kicked game can be logged: BET as real money, anything
              else as a paper pick (weeks 1-2 have no BETs at all, and the
              record should still capture what you would have bet). */}
          {
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <LogPickButton
                prefill={{
                  gameId: row.gameId,
                  away: row.away,
                  home: row.home,
                  line: check?.hrLine ?? line,
                  price: check?.hrUnderPrice ?? null,
                  verdict: v.verdict,
                  reason: v.reason,
                  gap: v.hrGap,
                  ev: check?.ev ?? null,
                  hrLine: check?.hrLine ?? null,
                  fairUnder: check?.marketFairUnder ?? null,
                }}
                picked={g.picked}
                kickedOff={g.kickedOff}
              />
            </div>
          }
        </div>
      </div>
    </div>
  );
}
