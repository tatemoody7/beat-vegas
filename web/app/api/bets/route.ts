import { NextRequest } from "next/server";

import { betsToCsv } from "@/lib/betLedger";
import { getBetLedger } from "@/lib/betLedgerDb";
import { viewerIsAuthed } from "@/lib/session";
import { gateLedger } from "@/lib/signalGate";

export const dynamic = "force-dynamic";

// CSV export of every bet in a season -- the Track record ledger as a file,
// with the stored clv and its displayed negation side by side. Same shape as
// /api/records: a bad season is a 400 with a reason, a database blip a 503.
export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("season");
  const season = raw === null || raw.trim() === "" ? NaN : Number(raw);
  if (!Number.isInteger(season) || season < 2000) {
    return new Response("bad season (integer year >= 2000 required)", {
      status: 400,
    });
  }
  let csv: string;
  try {
    // A visitor's file holds only rows whose game has kicked off.
    csv = betsToCsv(
      season,
      gateLedger(
        await getBetLedger(season),
        await viewerIsAuthed(),
        new Date(),
      ),
    );
  } catch (e) {
    console.error("[api/bets] getBetLedger failed:", e);
    return new Response("could not build the export — try again", {
      status: 503,
    });
  }
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="beatvegas-bets-${season}.csv"`,
    },
  });
}
