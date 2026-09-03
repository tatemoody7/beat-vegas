import { redirect } from "next/navigation";

// Moved: this view now lives on the board at `/`. Bookmarks still work.
// `?game=` is dropped on purpose: the board has no per-game target (movement is
// a section inside each card), so only season/week carry over.
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
