import { NextRequest, NextResponse } from "next/server";
import { getLedger } from "@/lib/ledger";

// GET /api/ledger?season=2025
export async function GET(req: NextRequest) {
  const season = Number(req.nextUrl.searchParams.get("season"));
  if (!Number.isFinite(season)) {
    return NextResponse.json(
      { error: "missing or invalid ?season" },
      { status: 400 },
    );
  }
  return NextResponse.json(await getLedger(season));
}
