import type { BoardFactor } from "@/lib/score";

// "What is behind it", as bars diverging from a centre line: right of centre
// helps the under, left hurts it, and the length is the factor's intensity.
//
// Ordering is by CREDIBILITY first, then strength. Sorting on intensity alone
// floated the unproven rows (travel, kickoff hour) to the top, because they
// happen to carry the largest intensities — which reads as though the
// speculative factors are the strongest evidence. Proven rows come first; the
// unproven ones follow, dimmed, because they are part of the score's story
// rather than evidence for it.

/** Half the track, so a full-strength factor reaches the edge from centre. */
const HALF = 50;

function tone(f: BoardFactor): string {
  if (f.color === "green") return "var(--good)";
  if (f.color === "red") return "var(--bad)";
  if (f.color === "amber") return "var(--warn)";
  return "var(--push)";
}

export default function FactorBars({ factors }: { factors: BoardFactor[] }) {
  const rows = [...factors]
    .filter((f) => f && f.key)
    .sort(
      (a, b) =>
        Number(a.hypothesis) - Number(b.hypothesis) ||
        b.intensity - a.intensity,
    );
  if (rows.length === 0) return null;
  const anyUnproven = rows.some((f) => f.hypothesis);
  // Raw intensity runs small (roughly 0.05-0.30), so scaling it straight to the
  // track drew six near-identical stubs. Normalising against the strongest
  // factor on this game makes the comparison — which is the only thing the bar
  // is for — actually visible. Lengths are relative within a game, never across.
  const peak = Math.max(...rows.map((f) => f.intensity), 0.0001);

  return (
    <div className="max-w-3xl">
      <div className="mb-2 flex justify-end">
        <div className="flex w-56 justify-between text-[0.6rem] uppercase tracking-[0.06em] text-[var(--text-dim)]">
          <span>hurts</span>
          <span>helps</span>
        </div>
      </div>

      <div className="space-y-2">
        {rows.map((f) => {
          const helps = f.lean > 0;
          const width = Math.max(4, Math.round((f.intensity / peak) * HALF));
          return (
            <div
              key={f.key}
              className={`flex items-center gap-3 ${f.hypothesis ? "opacity-60" : ""}`}
            >
              <span className="min-w-0 flex-1 text-xs text-[var(--text-muted)]">
                {f.sentence || `${f.label} — ${f.value}`}
                {f.hypothesis && (
                  <span className="bv-fac-badge bv-fac-badge-amber ml-2">
                    unproven
                  </span>
                )}
              </span>
              <span className="relative h-3 w-56 shrink-0">
                <span className="absolute inset-y-0 left-1/2 w-px bg-[var(--border)]" />
                <span
                  className="absolute top-0.5 h-2 rounded-sm"
                  style={{
                    background: tone(f),
                    left: helps ? "50%" : `${50 - width}%`,
                    width: `${width}%`,
                  }}
                />
              </span>
            </div>
          );
        })}
      </div>

      {anyUnproven && (
        <p className="mt-2 text-xs text-[var(--text-dim)]">
          {`Dimmed rows have not been checked against real lines yet.`}
        </p>
      )}
    </div>
  );
}
