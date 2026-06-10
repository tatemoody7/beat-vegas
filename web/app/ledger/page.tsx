import { getSeasons } from "@/lib/board";
import { getLedger, Record3 } from "@/lib/ledger";
import { getDecisionQuality } from "@/lib/decision-quality";
import SeasonSelect from "@/app/components/SeasonSelect";

export const dynamic = "force-dynamic";

const pct = (v: number | null | undefined) =>
  v == null ? "—" : `${v.toFixed(1)}%`;

function LedgerCard({
  title,
  rec,
  emptyHint,
}: {
  title: string;
  rec: Record3 | null;
  emptyHint: string;
}) {
  return (
    <div className="bv-card p-4">
      <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">{title}</h3>
      {rec === null ? (
        <p className="text-xs text-[var(--text-dim)]">{emptyHint}</p>
      ) : (
        <dl className="space-y-3">
          <div>
            <dt className="bv-stat-label" title="Share of bets that won.">
              Win rate
            </dt>
            <dd className="mt-0.5 font-[family-name:var(--font-display)] text-2xl font-extrabold tabular-nums text-[var(--text)]">
              {rec.hit}{" "}
              <span className="font-sans text-sm font-normal text-[var(--text-dim)]">
                {rec.record}
              </span>
            </dd>
          </div>
          <div className="flex gap-6">
            <div>
              <dt
                className="bv-stat-label"
                title="Profit in units. 1 unit = one standard bet."
              >
                Units
              </dt>
              <dd
                className="mt-0.5 font-mono text-lg font-semibold tabular-nums"
                style={{
                  color: rec.units.startsWith("-") ? "#dc2626" : "#16a34a",
                }}
              >
                {rec.units}
              </dd>
            </div>
            <div>
              <dt
                className="bv-stat-label"
                title="Average line value (CLV): did the line move our way after we'd bet? Positive = we beat the closing line."
              >
                Avg line value
              </dt>
              <dd className="mt-0.5 font-mono text-lg font-semibold tabular-nums text-[var(--text-muted)]">
                {rec.clv}
              </dd>
            </div>
          </div>
        </dl>
      )}
    </div>
  );
}

export default async function LedgerPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());

  const { market, model, you, picks } = await getLedger(season);
  const dq = await getDecisionQuality(season);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="bv-page-title">Ledger</h1>
        {seasons.length > 0 && (
          <SeasonSelect seasons={seasons} current={season} />
        )}
      </div>
      <p className="bv-page-sub mb-5">
        Settled results for {season} · Market = how the under did at the closing
        line (the final line before kickoff) · Model = the model&apos;s under
        picks · You = your own logged bets.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <LedgerCard
          title="Market"
          rec={market}
          emptyHint="Fills in once games are settled."
        />
        <LedgerCard
          title="Model"
          rec={model}
          emptyHint="Fills in once the week is scored and settled."
        />
        <LedgerCard title="You" rec={you} emptyHint="Log bets in My Picks." />
      </div>

      <h2 className="mb-2 mt-7 text-sm font-semibold text-[var(--text)]">
        Your bets
      </h2>
      {picks.length === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No logged picks for {season}.
        </p>
      ) : (
        <div className="bv-table-wrap">
          <table className="bv-table">
            <thead>
              <tr>
                <th>Wk</th>
                <th>Matchup</th>
                <th>Line</th>
                <th title="The odds / price (e.g. −110).">Odds</th>
                <th>Result</th>
                <th title="Profit in units. 1 unit = one standard bet.">
                  Units
                </th>
                <th title="Line value (CLV): positive = the line moved our way after we'd bet.">
                  Line value
                </th>
              </tr>
            </thead>
            <tbody>
              {picks.map((p, i) => (
                <tr key={i}>
                  <td className="text-[var(--text-muted)]">{p.week ?? "—"}</td>
                  <td className="text-[var(--text)]">
                    {p.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                    {p.home}
                  </td>
                  <td className="text-[var(--text-muted)]">
                    {p.line !== null ? `under ${p.line}` : "—"}
                  </td>
                  <td className="text-[var(--text-dim)]">{p.price ?? "—"}</td>
                  <td>
                    <span
                      style={{
                        color:
                          p.result === "under"
                            ? "#16a34a"
                            : p.result === "over"
                              ? "#dc2626"
                              : "#9ca3af",
                      }}
                    >
                      {p.result}
                    </span>
                  </td>
                  <td
                    className="font-mono"
                    style={{
                      color:
                        p.units === null
                          ? "#9ca3af"
                          : p.units >= 0
                            ? "#16a34a"
                            : "#dc2626",
                    }}
                  >
                    {p.units !== null
                      ? `${p.units >= 0 ? "+" : ""}${p.units.toFixed(2)}`
                      : "—"}
                  </td>
                  <td className="font-mono text-[var(--text-muted)]">
                    {p.clv !== null
                      ? `${p.clv >= 0 ? "+" : ""}${p.clv.toFixed(2)}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="mb-2 mt-7 text-sm font-semibold text-[var(--text)]">
        Decision quality
      </h2>
      {dq.n === 0 ? (
        <p className="bv-card p-4 text-sm text-[var(--text-muted)]">
          No graded picks yet. Log picks to see whether your calls beat your
          model, beat the close, and which factors you lean on well.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Beat my model
              </h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Hit% when your model agreed (market line above our line)."
                  >
                    With model
                  </dt>
                  <dd>
                    {pct(dq.beatModel.agreed.hitPct)} ({dq.beatModel.agreed.n})
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Hit% when you picked against your model."
                  >
                    Against model
                  </dt>
                  <dd>
                    {pct(dq.beatModel.against.hitPct)} ({dq.beatModel.against.n}
                    )
                  </dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Beat the close
              </h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Average closing line value."
                  >
                    Avg CLV
                  </dt>
                  <dd>{dq.clv.avg == null ? "—" : dq.clv.avg.toFixed(2)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks with positive CLV."
                  >
                    % positive
                  </dt>
                  <dd>{pct(dq.clv.pctPositive)}</dd>
                </div>
              </dl>
            </div>
            <div className="bv-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-[var(--text)]">
                Timing
              </h3>
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks taken at or above the opening line."
                  >
                    ≥ open
                  </dt>
                  <dd>{pct(dq.timing.pctAtOrBetterThanOpen)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt
                    className="bv-stat-label"
                    title="Share of picks with a better number than the close."
                  >
                    Beat close
                  </dt>
                  <dd>{pct(dq.timing.pctBeatingClose)}</dd>
                </div>
              </dl>
            </div>
          </div>
          {dq.factors.length > 0 && (
            <div className="bv-table-wrap mt-3">
              <table className="bv-table">
                <thead>
                  <tr>
                    <th>Factor</th>
                    <th>Your n</th>
                    <th>Your hit%</th>
                    <th>Ledger hit%</th>
                    <th>Weighting</th>
                  </tr>
                </thead>
                <tbody>
                  {dq.factors.map((f) => (
                    <tr key={f.key}>
                      <td>{f.label}</td>
                      <td>{f.n}</td>
                      <td>{pct(f.yourHitPct)}</td>
                      <td>
                        {f.ledgerHitPct == null ? "—" : pct(f.ledgerHitPct)}
                      </td>
                      <td>
                        <span className="bv-pill">
                          {f.weight === "even"
                            ? "balanced"
                            : f.weight === "under"
                              ? "use well"
                              : "over-lean"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
