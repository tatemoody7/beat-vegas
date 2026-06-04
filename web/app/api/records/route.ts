import { NextRequest } from "next/server";

import { getSeasonRecords, recordsToCsv } from "@/lib/records";

export const dynamic = "force-dynamic";

// CSV export of a season's records (opens in Excel/Sheets). XLSX is a future
// add (needs a spreadsheet lib); CSV imports natively into both.
export async function GET(req: NextRequest) {
  const season = Number(req.nextUrl.searchParams.get("season"));
  if (!Number.isFinite(season)) {
    return new Response("bad season", { status: 400 });
  }
  const rows = await getSeasonRecords(season);
  const csv = recordsToCsv(rows);
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="beatvegas-records-${season}.csv"`,
    },
  });
}
