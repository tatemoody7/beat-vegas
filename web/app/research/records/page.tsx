import { redirect } from "next/navigation";

// The records table moved under Track record. Kept as a redirect so old links
// and bookmarks (including ?season=) still land in the right place.
export default async function Moved({
  searchParams,
}: {
  searchParams: Promise<{ season?: string }>;
}) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.season) qs.set("season", sp.season);
  const q = qs.toString();
  redirect(q ? `/proof/records?${q}` : "/proof/records");
}
