import { NextResponse } from "next/server";
import { getEdgeStats, getModelRuns } from "@/lib/research";

// GET /api/research — edge stats + model_runs over time.
export async function GET() {
  const [edge, runs] = await Promise.all([getEdgeStats(), getModelRuns()]);
  return NextResponse.json({ edge, runs });
}
