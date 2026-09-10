import type { ReactNode } from "react";
import { gradeColor, gradeWord, type Settled } from "@/lib/grade";

// The card's headline block, in one of three states. Before kickoff it is the
// game's place on the board (#1 = best game of the week) over the tier word,
// coloured by the score band (70+ green, 55–69 amber, under 55 red). Once the
// game starts there is no decision left, so it reads LIVE in grey; once it
// settles it reads the result in the result's colour. Never cyan: cyan is
// chrome. The 0–100 score itself lives inside the card, under "Our number".

type Props = {
  /** 0–100; sets the colour before kickoff. */
  score: number | null;
  /** Place on the board this week; null once the game has kicked off. */
  rank: number | null;
  /** The game has started. */
  kickedOff: boolean;
  /** Once known, the result colours the badge and replaces the rank. */
  settled?: Settled | null;
  /** Optional word under the rank (the tier); defaults to the grade word. */
  label?: string | null;
  className?: string;
};

/** Every state is the same box, so a column of badges never goes ragged. */
function Box({
  color,
  aria,
  className,
  children,
}: {
  color: string;
  aria: string;
  className: string;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex min-h-[2.9rem] w-14 shrink-0 flex-col items-center justify-center rounded-[var(--r-sm)] px-1 py-1 ${className}`}
      style={{ background: `var(--${color})`, color: "var(--badge-ink)" }}
      aria-label={aria}
    >
      {children}
    </span>
  );
}

const WORD = "text-[0.6rem] font-bold uppercase tracking-wide";

export default function ScoreBadge({
  score,
  rank,
  kickedOff,
  settled = null,
  label,
  className = "",
}: Props) {
  if (settled !== null) {
    const result = gradeWord(score, settled);
    return (
      <Box
        color={gradeColor(score, settled)}
        aria={result}
        className={className}
      >
        <span className={WORD}>{result}</span>
      </Box>
    );
  }
  if (kickedOff) {
    return (
      <Box color="push" aria="Kicked off" className={className}>
        <span className={WORD}>Live</span>
      </Box>
    );
  }
  const tier = label ?? gradeWord(score, null);
  return (
    <Box
      color={gradeColor(score, null)}
      aria={rank === null ? `Unranked, ${tier}` : `Rank ${rank}, ${tier}`}
      className={className}
    >
      <span className="font-[family-name:var(--font-display)] text-2xl font-extrabold leading-none tabular-nums">
        {rank === null ? "—" : `#${rank}`}
      </span>
      <span className={`mt-0.5 ${WORD}`}>{tier}</span>
    </Box>
  );
}
