import Link from "next/link";
import type { ThisWeekGame } from "@/lib/thisWeek";
import { CONFIDENCE_LABEL, type Confidence, type Verdict } from "@/lib/verdict";

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
      title="How sure the system is: three dots = model edge well outside its margin of error at a good price; one dot = a small lean or a price-only edge; none = no read."
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
          {v.verdict !== "PASS" && (
            <div className="mt-3 flex flex-wrap gap-3 text-xs">
              <Link href="/picks" className="bv-nav-link">
                Log this pick →
              </Link>
              <Link href="/preview" className="bv-nav-link">
                Check injuries →
              </Link>
              <Link href="/line-check" className="bv-nav-link">
                All books →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
