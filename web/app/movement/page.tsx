import { getSeasons } from "@/lib/board";
import { getMovement, getMovementGames } from "@/lib/movement";
import SeasonSelect from "@/app/components/SeasonSelect";
import GameSelect from "@/app/components/GameSelect";
import MovementChart from "@/app/components/MovementChart";

export const dynamic = "force-dynamic";

export default async function MovementPage({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; game?: string }>;
}) {
  const seasons = await getSeasons();
  const sp = await searchParams;
  const requested = sp.season ? Number(sp.season) : NaN;
  const season =
    Number.isFinite(requested) && seasons.includes(requested)
      ? requested
      : (seasons[0] ?? new Date().getFullYear());

  const games = await getMovementGames(season);
  const requestedGame = sp.game ? Number(sp.game) : NaN;
  const selected =
    Number.isFinite(requestedGame) && games.some((g) => g.id === requestedGame)
      ? requestedGame
      : (games[0]?.id ?? null);

  const movement = selected !== null ? await getMovement(selected) : null;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="bv-page-title">Line Movement</h1>
          <p className="bv-page-sub">
            First-half line at each sportsbook over time — {season}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {games.length > 0 && selected !== null && (
            <GameSelect games={games} current={selected} />
          )}
          {seasons.length > 0 && (
            <SeasonSelect seasons={seasons} current={season} />
          )}
        </div>
      </div>

      {!movement || movement.points.length === 0 ? (
        <p className="bv-card p-6 text-sm text-[var(--text-muted)]">
          Nothing to chart for {season} yet — a movement chart appears once a
          game&apos;s line has been checked more than once.
        </p>
      ) : (
        <div className="flex flex-col gap-5">
          <MovementChart points={movement.points} books={movement.books} />

          <div className="bv-table-wrap">
            <table className="bv-table">
              <thead>
                <tr>
                  <th>When checked</th>
                  <th>Sportsbook</th>
                  <th>Line</th>
                </tr>
              </thead>
              <tbody>
                {movement.rows.map((r, i) => (
                  <tr key={i}>
                    <td className="text-[var(--text-muted)]">
                      {r.captured_at}
                    </td>
                    <td className="text-[var(--text-muted)]">{r.book}</td>
                    <td className="font-mono text-[var(--text)]">{r.line}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
