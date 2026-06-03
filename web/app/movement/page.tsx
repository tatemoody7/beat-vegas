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
    <div className="mx-auto max-w-4xl">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Line Movement</h1>
          <p className="text-sm text-gray-500">
            First-half line at each sportsbook over time — {season}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          {games.length > 0 && selected !== null && (
            <GameSelect games={games} current={selected} />
          )}
          {seasons.length > 0 && <SeasonSelect seasons={seasons} current={season} />}
        </div>
      </div>

      {!movement || movement.points.length === 0 ? (
        <p className="rounded-lg border border-gray-800 bg-gray-900 p-6 text-sm text-gray-400">
          Nothing to chart for {season} yet — a movement chart appears once a game's
          line has been checked more than once.
        </p>
      ) : (
        <div className="flex flex-col gap-5">
          <MovementChart points={movement.points} books={movement.books} />

          <div className="overflow-x-auto rounded-xl border border-gray-800">
            <table className="w-full text-sm">
              <thead className="bg-gray-900 text-left text-gray-400">
                <tr>
                  <th className="px-3 py-2 font-medium">When checked</th>
                  <th className="px-3 py-2 font-medium">Sportsbook</th>
                  <th className="px-3 py-2 font-medium">Line</th>
                </tr>
              </thead>
              <tbody>
                {movement.rows.map((r, i) => (
                  <tr key={i} className="border-t border-gray-800">
                    <td className="px-3 py-1.5 text-gray-400">{r.captured_at}</td>
                    <td className="px-3 py-1.5 text-gray-300">{r.book}</td>
                    <td className="px-3 py-1.5 text-gray-200">{r.line}</td>
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
