import { NextRequest, NextResponse } from "next/server";
import { getLineStudy } from "@/lib/lineStudy";

// GET /api/line-study?season=2025&minGames=30
export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const season = Number(sp.get("season"));
  const minGames = sp.get("minGames") ? Number(sp.get("minGames")) : 30;
  if (!Number.isFinite(season)) {
    return NextResponse.json(
      { error: "missing or invalid ?season" },
      { status: 400 },
    );
  }
  const data = await getLineStudy(season, minGames);
  return NextResponse.json(data);
}
