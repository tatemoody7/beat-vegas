import { redirect } from "next/navigation";

// Moved: this view now lives at /research (nav consolidation). Bookmarks still work.
export default async function Moved({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string; minGames?: string }>;
}) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (sp.season) q.set("season", sp.season);
  if (sp.week) q.set("week", sp.week);
  if (sp.minGames) q.set("minGames", sp.minGames);
  const qs = q.toString();
  redirect(`/proof${qs ? `?${qs}` : ""}`);
}
