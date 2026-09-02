import { redirect } from "next/navigation";

// Moved: this view now lives at / (nav consolidation). Bookmarks still work.
export default async function Moved({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (sp.season) q.set("season", sp.season);
  if (sp.week) q.set("week", sp.week);
  const qs = q.toString();
  redirect(`/${qs ? `?${qs}` : ""}`);
}
