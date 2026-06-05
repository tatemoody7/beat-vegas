import { getSeasons } from "@/lib/board";
import { getPreview } from "@/lib/preview";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

function TeamBlock({
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
      <div className="mb-1 text-sm font-semibold text-[var(--text)]">{team}</div>
      {injuries.length > 0 && (
        <ul className="mb-2 space-y-0.5">
          {injuries.map((i, k) => (
            <li key={k} className="text-xs text-[var(--over-lean)]">
              {i}
            </li>
          ))}
        </ul>
      )}
      {news.length > 0 ? (
        <ul className="space-y-0.5">
          {news.map((n, k) => (
            <li key={k} className="text-xs text-[var(--text-muted)]">
              • {n}
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

export default async function PreviewPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());
  const wantWeek = sp.week ? Number(sp.week) : undefined;

  const preview = await getPreview(season, wantWeek);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Week Preview</h1>
          <p className="bv-page-sub">
            This week&apos;s games with the latest news and injuries — the
            research read before lines drop. Display only (unofficial ESPN).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {preview.weeks.length > 0 && preview.week !== null && (
            <WeekSelect weeks={preview.weeks} current={preview.week} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      {preview.games.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          No preview built for {season} yet. Run{" "}
          <code className="text-[var(--text)]">scripts/research_preview.py</code>{" "}
          early in the week to pull the slate&apos;s news and injuries.
        </p>
      ) : (
        <div className="grid gap-4">
          {preview.games.map((g) => (
            <div key={g.gameId} className="bv-card p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div className="text-base font-semibold text-[var(--text)]">
                  {g.away} <span className="text-[var(--text-dim)]">@</span>{" "}
                  {g.home}
                </div>
                {g.qbOut && (
                  <span
                    className="bv-pill"
                    style={{ color: "var(--over)", borderColor: "var(--over)" }}
                    title={g.qbOutDetail ?? "Starting QB listed out"}
                  >
                    ⚠ QB out
                  </span>
                )}
              </div>
              {g.qbOut && g.qbOutDetail && (
                <p className="mb-3 text-xs text-[var(--over-lean)]">
                  {g.qbOutDetail}
                </p>
              )}
              <div className="flex flex-col gap-4 sm:flex-row">
                <TeamBlock
                  team={g.away}
                  news={g.awayNews}
                  injuries={g.awayInjuries}
                />
                <TeamBlock
                  team={g.home}
                  news={g.homeNews}
                  injuries={g.homeInjuries}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
