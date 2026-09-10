import { fmt, signed } from "@/lib/format";
import { BET_GAP_PTS } from "@/lib/verdict";

// The gap, drawn. Our number and the line sit on one short axis; the span
// between them IS the gap, split at the BET_GAP_PTS bar so you can see how much
// of it clears. Grey is the part you must clear to bet at all, green is the
// surplus, red means the line sits below our number (that leans over, and we
// only bet unders). The tick is the kill line — the number it stops being a bet.
//
// Colour follows the grade language in globals.css: --good clears, --bad leans
// the wrong way. Cyan never appears here; it is chrome only.

const PAD = 2; // points of breathing room either side of the outermost mark

export default function GapBar({
  ourNumber,
  line,
  killLine,
  lineLabel,
}: {
  ourNumber: number | null;
  /** The line the gap is measured against (Hard Rock, else market, else ours). */
  line: number | null;
  killLine?: number | null;
  /** Which line this is, in words — from labels.ts basisPhrase. */
  lineLabel: string;
}) {
  // Without both numbers there is no gap to draw, and a half-drawn axis would
  // imply one. The caller shows the "no model number" / "no line yet" copy.
  if (ourNumber === null || line === null) return null;

  const gap = Math.round((line - ourNumber) * 100) / 100;
  const bar = ourNumber + BET_GAP_PTS; // the number the line must beat to be a bet
  const kill = killLine ?? null;

  const marks = [ourNumber, line, bar, ...(kill === null ? [] : [kill])];
  const lo = Math.min(...marks) - PAD;
  const hi = Math.max(...marks) + PAD;
  const pct = (v: number) => ((v - lo) / (hi - lo)) * 100;

  // Positive gap: grey up to the bar, green beyond it. Negative: one red span
  // running back from our number to the line.
  const clears = gap >= BET_GAP_PTS;
  const needEnd = Math.min(line, bar);

  return (
    <div className="w-full">
      {/* Explicit geometry so the value labels clear their own tick marks:
          label 0-16, ticks 20-44, track 29-35, captions at the bottom. */}
      <div className="relative h-16">
        <div className="absolute inset-x-0 top-[29px] h-1.5 rounded-full bg-[var(--bg-2)]" />

        {gap > 0 ? (
          <>
            <div
              className="absolute top-[29px] h-1.5 bg-[var(--border-strong)]"
              style={{
                left: `${pct(ourNumber)}%`,
                width: `${Math.max(0, pct(needEnd) - pct(ourNumber))}%`,
              }}
            />
            {clears && (
              <div
                className="absolute top-[29px] h-1.5 bg-[var(--good)]"
                style={{
                  left: `${pct(bar)}%`,
                  width: `${pct(line) - pct(bar)}%`,
                }}
              />
            )}
          </>
        ) : (
          <div
            className="absolute top-[29px] h-1.5 bg-[var(--bad)]"
            style={{
              left: `${pct(line)}%`,
              width: `${Math.max(0, pct(ourNumber) - pct(line))}%`,
            }}
          />
        )}

        {kill !== null && (
          <div
            className="absolute top-[22px] h-5 w-px bg-[var(--text-muted)]"
            style={{ left: `${pct(kill)}%` }}
            aria-hidden
          />
        )}

        <Mark at={pct(ourNumber)} value={ourNumber} caption="our number" />
        <Mark at={pct(line)} value={line} caption="the line" />

        {kill !== null && (
          <span
            className="absolute bottom-0 -translate-x-1/2 whitespace-nowrap text-[0.6rem] text-[var(--text-dim)]"
            style={{ left: `${pct(kill)}%` }}
          >
            {`kill ${fmt(kill)}`}
          </span>
        )}
      </div>

      {/* Arithmetic only. The verdict sentence sits below the bar and must not
          be said twice. */}
      <p className="mt-1 text-xs text-[var(--text-muted)]">
        {gap <= 0
          ? `The line sits ${fmt(Math.abs(gap), 1)} below our number.`
          : clears
            ? `${signed(gap, 1)} ${lineLabel} — clears the ${BET_GAP_PTS}-point bar by ${fmt(gap - BET_GAP_PTS, 1)}.`
            : `${signed(gap, 1)} ${lineLabel} — ${fmt(BET_GAP_PTS - gap, 1)} short of the ${BET_GAP_PTS}-point bar.`}
      </p>
    </div>
  );
}

function Mark({
  at,
  value,
  caption,
}: {
  at: number;
  value: number;
  caption: string;
}) {
  return (
    <>
      <div
        className="absolute top-[20px] h-6 w-0.5 bg-[var(--text)]"
        style={{ left: `${at}%` }}
        aria-hidden
      />
      <span
        className="absolute top-0 -translate-x-1/2 whitespace-nowrap font-mono text-xs text-[var(--text)]"
        style={{ left: `${at}%` }}
      >
        {fmt(value)}
      </span>
      <span
        className="absolute bottom-0 -translate-x-1/2 whitespace-nowrap text-[0.6rem] uppercase tracking-[0.06em] text-[var(--text-dim)]"
        style={{ left: `${at}%` }}
      >
        {caption}
      </span>
    </>
  );
}
