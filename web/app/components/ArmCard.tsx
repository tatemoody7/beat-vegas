import { etDateLabel } from "@/lib/et";
import type { HypothesisCard } from "@/lib/research";
import { PROTOCOL, pct } from "@/lib/research";

// One registered hypothesis, as the Research page shows it (Option A, Tate's
// call 2026-10-14): what it tests, where it stands against ITS OWN standard
// (readings of 30 for a paper arm, forward opportunities of 40 for the
// pricing study), the judge's EV only once there is enough to read, and when
// it was last read. No rank, no colour that implies a winner before the first
// decision window; "not enough data" is a status, not a failure.

const STATUS_CLASS: Record<string, string> = {
  promoted: "bv-badge--accent",
  strengthening: "bv-badge--accent",
  stopped: "bv-badge--warn",
  weakening: "bv-badge--warn",
  "timed out": "bv-badge--warn",
};

export default function ArmCard({
  card,
  authed = false,
}: {
  card: HypothesisCard;
  /** Signed in: the run id is the owner's detail (Q7). */
  authed?: boolean;
}) {
  const { meta } = card;
  const unit = meta.standard === "pricing" ? "opportunities" : "readings";
  const evLine =
    card.ev === null
      ? card.readings === 0
        ? "EV vs close: nothing read yet"
        : `EV vs close: not enough data (${card.readings} of ${PROTOCOL.EV_INTERVAL_MIN_READINGS} to show one)`
      : card.ev.lo === null || card.ev.hi === null
        ? `EV vs close ${pct(card.ev.mean)} (interval needs more)`
        : `EV vs close ${pct(card.ev.mean)} (${pct(card.ev.lo)} to ${pct(card.ev.hi)})`;
  return (
    <article
      aria-label={meta.name}
      data-hypothesis={meta.id}
      data-status={card.status}
      className="bv-card flex flex-col gap-2 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-[var(--text)]">
          {meta.name}
        </h3>
        <div className="flex flex-wrap gap-1.5">
          <span
            className={`bv-badge ${STATUS_CLASS[card.status] ?? "bv-badge--push"}`}
            data-testid="status"
          >
            {card.status}
          </span>
          {card.outdated && (
            <span className="bv-badge bv-badge--warn">outdated</span>
          )}
        </div>
      </div>
      <p className="text-sm leading-relaxed text-[var(--text-muted)]">
        {meta.rule}
      </p>
      <div
        role="progressbar"
        aria-label={`${unit} toward the first decision`}
        aria-valuemin={0}
        aria-valuemax={card.needed}
        aria-valuenow={Math.min(card.readings, card.needed)}
        className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-2)]"
      >
        <div
          className="h-full bg-[var(--accent)]"
          style={{ width: `${card.progressPct}%` }}
        />
      </div>
      <p className="font-mono text-xs text-[var(--text-muted)]">
        {`${card.readings} of ${card.needed} ${unit}`}
        {meta.standard === "sprt" && card.weeks !== null
          ? ` · ${card.weeks} week${card.weeks === 1 ? "" : "s"} of ${PROTOCOL.MIN_WEEKS}`
          : ""}
        {` · ${card.excluded} excluded`}
        {card.pending > 0 ? ` · ${card.pending} pending` : ""}
        {` · ${card.logged} logged`}
      </p>
      <p className="text-xs text-[var(--text-dim)]" data-testid="standard">
        {meta.standard === "pricing"
          ? `Reads a direction after ${PROTOCOL.PRICING_NEEDED} forward opportunities.`
          : `Promoted or stopped only after ${PROTOCOL.NEEDED_READINGS} readings over ${PROTOCOL.MIN_WEEKS} or more weeks.`}
      </p>
      <p className="text-sm text-[var(--text)]">{evLine}</p>
      {card.llrPct !== null && card.llr !== null && (
        <div>
          <div className="flex justify-between text-[0.65rem] uppercase tracking-[0.08em] text-[var(--text-dim)]">
            <span>stop</span>
            <span>{`LLR ${card.llr >= 0 ? "+" : ""}${card.llr.toFixed(2)}`}</span>
            <span>promote</span>
          </div>
          <div
            aria-label="position between the stop and promote boundaries"
            className="relative mt-1 h-1.5 w-full rounded-full bg-[var(--bg-2)]"
          >
            <span
              aria-hidden="true"
              className="absolute top-1/2 h-3 w-1 -translate-x-1/2 -translate-y-1/2 rounded-sm bg-[var(--text)]"
              style={{ left: `${Math.round(100 * card.llrPct)}%` }}
            />
          </div>
        </div>
      )}
      <p className="text-xs text-[var(--text-dim)]">
        {card.readAt === null
          ? "Not yet read."
          : `Last read ${etDateLabel(card.readAt)}${authed && card.runId && card.runId !== "-" ? ` · run ${card.runId}` : ""}`}
        {card.nextRead ? ` · Next read ${etDateLabel(card.nextRead)}` : ""}
      </p>
    </article>
  );
}
