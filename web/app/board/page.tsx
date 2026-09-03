import { redirect } from "next/navigation";

// The board moved to the home page. Kept as a redirect so old links and
// bookmarks (including ?week=/?season=) still land in the right place.
export default async function BoardRedirect({
  searchParams,
}: {
  searchParams: Promise<{ season?: string; week?: string }>;
}) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.season) qs.set("season", sp.season);
  if (sp.week) qs.set("week", sp.week);
  const q = qs.toString();
  redirect(q ? `/?${q}` : "/");
}
