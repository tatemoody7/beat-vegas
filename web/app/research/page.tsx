import { redirect } from "next/navigation";

// Research retired into Track record: the calibration table, the method stats
// and the line study all live on /proof now, and the gap-vs-line-value table
// was dropped (its buckets were n=1, and the win-rate-by-gap bands answer a
// sharper version of the same question). Kept as a redirect so old links and
// bookmarks still land somewhere useful.
export default async function Moved({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; minGames?: string }>;
}) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.season) qs.set("season", sp.season);
  if (sp.minGames) qs.set("minGames", sp.minGames);
  const q = qs.toString();
  redirect(q ? `/proof?${q}` : "/proof");
}
