import { NextRequest, NextResponse } from "next/server";
import { getBoard } from "@/lib/board";

// GET /api/board?season=2025 — same data the board page renders (parity with the
// Streamlit q() calls; available for future client-side use).
export async function GET(req: NextRequest) {
  const seasonParam = req.nextUrl.searchParams.get("season");
  const season = seasonParam ? Number(seasonParam) : NaN;
  if (!Number.isFinite(season)) {
    return NextResponse.json(
      { error: "missing or invalid ?season" },
      { status: 400 },
    );
  }
  const rows = await getBoard(season);
  return NextResponse.json(rows);
}
