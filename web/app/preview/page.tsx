import { getSeasons } from "@/lib/board";
import { getPreview } from "@/lib/preview";
import { resolveSeason } from "@/lib/season";
import SeasonFallbackNotice from "@/app/components/SeasonFallbackNotice";
import SeasonSelect from "@/app/components/SeasonSelect";
import WeekSelect from "@/app/components/WeekSelect";

export const dynamic = "force-dynamic";

// An injury string is "POS Name — Status". Only an actual absence (out/doubtful/
// questionable/suspended) warrants the alert color; available players stay neutral.
const ALERT_STATUS =
  /\b(out|doubtful|questionable|suspended|injured reserve|ir)\b/i;
function injuryColor(line: string): string {
  return ALERT_STATUS.test(line) ? "var(--over-lean)" : "var(--text-muted)";
}

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
      <div className="mb-1 text-sm font-semibold text-[var(--text)]">
        {team}
      </div>
      {injuries.length > 0 && (
        <ul className="mb-2 space-y-0.5">
          {injuries.map((i, k) => (
            <li key={k} className="text-xs" style={{ color: injuryColor(i) }}>
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
  const { season, fallbackFrom } = resolveSeason(seasons, sp.season);
  const wantWeek = sp.week ? Number(sp.week) : undefined;

  const preview = await getPreview(season, wantWeek);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Week Preview</h1>
          <p className="bv-page-sub">
            This week’s games with the latest news and injuries — the research
            read before lines drop. Display only: injuries from Rotowire’s
            college report (conference availability reports plus beat
            reporting), news from ESPN. Both unofficial; check starters before
            any real bet.
          </p>
          {preview.games[0]?.updatedAt && (
            <p className="mt-1 text-xs text-[var(--text-dim)]">
              {`Last pulled ${new Date(preview.games[0].updatedAt.replace(" ", "T") + "Z").toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "2-digit" })} ET — refreshes Tuesday and Friday mornings.`}
            </p>
          )}
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

      <SeasonFallbackNotice fallbackFrom={fallbackFrom} season={season} />

      {preview.games.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          {`No preview for ${season} yet. News and injuries are pulled automatically on Tuesday and Friday mornings.`}
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
