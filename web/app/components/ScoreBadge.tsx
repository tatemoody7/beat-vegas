import { gradeColor, gradeWord, type Settled } from "@/lib/grade";

// The grade, as one coloured number. Colour = the result once the game has
// settled (won green / lost red / push grey), else the score band (70+ green,
// 55–69 amber, under 55 red). The word beside it carries the same meaning for
// readers who cannot see the colour. Never cyan: cyan is chrome.

type Props = {
  /** 0–100; null renders a dash. */
  score: number | null;
  /** Once known, the result colours the badge instead of the score. */
  settled?: Settled | null;
  /** lg = the card headline; sm = a table row or chip. */
  size?: "lg" | "sm";
  /** Optional secondary word (e.g. the tier); defaults to the grade/result word. */
  label?: string | null;
  className?: string;
};

const COLOR_CLASS = {
  good: "bv-badge--good",
  warn: "bv-badge--warn",
  bad: "bv-badge--bad",
  push: "bv-badge--push",
} as const;

export default function ScoreBadge({
  score,
  settled = null,
  size = "lg",
  label,
  className = "",
}: Props) {
  const color = gradeColor(score, settled);
  const word = label ?? gradeWord(score, settled);
  const text = score === null ? "—" : String(Math.round(score));
  const aria =
    score === null
      ? `No score, ${word}`
      : `Score ${Math.round(score)}, ${word}`;
  if (size === "sm") {
    return (
      <span
        className={`bv-badge ${COLOR_CLASS[color]} ${className}`}
        aria-label={aria}
      >
        <span className="font-mono font-bold tabular-nums">{text}</span>
        <span className="opacity-90">{word}</span>
      </span>
    );
  }
  return (
    <span
      className={`inline-flex w-14 shrink-0 flex-col items-center justify-center rounded-[var(--r-sm)] px-1 py-1 ${className}`}
      style={{
        background: `var(--${color})`,
        color: "var(--badge-ink)",
      }}
      aria-label={aria}
    >
      <span className="font-[family-name:var(--font-display)] text-2xl font-extrabold leading-none tabular-nums">
        {text}
      </span>
      <span className="mt-0.5 text-[0.6rem] font-bold uppercase tracking-wide">
        {word}
      </span>
    </span>
  );
}
