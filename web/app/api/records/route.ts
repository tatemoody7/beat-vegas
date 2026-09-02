import { NextRequest } from "next/server";

import { getSeasonRecords, recordsToCsv } from "@/lib/records";

export const dynamic = "force-dynamic";

// CSV export of a season's records (opens in Excel/Sheets). XLSX is a future
// add (needs a spreadsheet lib); CSV imports natively into both.
export async function GET(req: NextRequest) {
  // Number(null) is 0 and Number("2025.5") is finite — require a real season.
  const raw = req.nextUrl.searchParams.get("season");
  const season = raw === null || raw.trim() === "" ? NaN : Number(raw);
  if (!Number.isInteger(season) || season < 2000) {
    return new Response("bad season (integer year >= 2000 required)", {
      status: 400,
    });
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
