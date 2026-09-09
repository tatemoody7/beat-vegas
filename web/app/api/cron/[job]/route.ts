import { NextRequest, NextResponse } from "next/server";

import {
  cronJobFor,
  dispatchBody,
  dispatchDecision,
  GITHUB_REPO,
  suppressedBy,
  windowOpenInstant,
  type CronJob,
  type RunSummary,
} from "@/lib/cronJobs";
import { etClock12 } from "@/lib/et";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

// GET /api/cron/[job] — Vercel's scheduler calls this; it dispatches the
// GitHub workflow. See lib/cronJobs.ts for why the trigger moved here.
//
// EXEMPT FROM THE PASSWORD GATE (middleware.ts): Vercel's cron carries no
// session cookie, so without that exemption every invocation would come back
// 401, Vercel would record it as completed, and nothing would ever build while
// the dashboard looked healthy. CRON_SECRET is therefore the ONLY lock on this
// route — an unset or leaked value makes it a public button that spends Odds
// API credits, which is why a missing secret fails closed with a 500.

const GITHUB_API = "https://api.github.com";
const TIMEOUT_MS = 8_000;
/** Prefer a missing card to a duplicate build: a missing card costs the betting
 *  day, a duplicate costs credits against a guard that already exists. */
const DISPATCH_WHEN_PROBE_FAILS = true;

type Result = {
  dispatched: boolean;
  workflow: string | null;
  slot: string | null;
  reason: string;
  githubStatus?: number;
};

function ghHeaders(token: string): Record<string, string> {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    // GitHub rejects a request with no User-Agent (403); Node's fetch sets none.
    "User-Agent": "beat-vegas-vercel-cron",
  };
}

/** Constant-time-ish compare so the secret is not learnable byte by byte. */
function secretsMatch(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function recentRuns(
  job: CronJob,
  now: Date,
  token: string,
): Promise<RunSummary[]> {
  const since = windowOpenInstant(job, now).toISOString();
  const url =
    `${GITHUB_API}/repos/${GITHUB_REPO}/actions/workflows/${job.workflow}/runs` +
    `?created=%3E%3D${encodeURIComponent(since)}&per_page=20&exclude_pull_requests=true`;
  const resp = await fetch(url, {
    headers: ghHeaders(token),
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!resp.ok) throw new Error(`runs query ${resp.status}`);
  const data = (await resp.json()) as { workflow_runs?: RunSummary[] };
  return data.workflow_runs ?? [];
}

function json(status: number, body: Result, req: NextRequest, id: string) {
  console.log(
    JSON.stringify({
      tag: "cron-dispatch",
      job: id,
      status,
      ...body,
      etClock: etClock12(new Date()),
      schedule: req.headers.get("x-vercel-cron-schedule"),
    }),
  );
  return NextResponse.json(body, { status });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ job: string }> },
) {
  const now = new Date();
  const { job: id } = await params;
  const job = cronJobFor(id);
  const base = { dispatched: false, workflow: null, slot: null } as const;

  if (job === null) {
    return json(404, { ...base, reason: `unknown job '${id}'` }, req, id);
  }
  const slot = job.inputs.slot ?? null;
  const named = { dispatched: false, workflow: job.workflow, slot };

  // 1. Auth. Fail CLOSED when the secret is not configured: a 200 here would
  //    read as a routine no-op in the dashboard while the route sat open.
  const secret = process.env.CRON_SECRET;
  if (!secret) {
    console.error("[cron] CRON_SECRET is not configured — refusing to serve");
    return json(
      500,
      { ...named, reason: "CRON_SECRET not configured" },
      req,
      id,
    );
  }
  const header = req.headers.get("authorization") ?? "";
  if (!header.startsWith("Bearer ") || !secretsMatch(header.slice(7), secret)) {
    return json(401, { ...named, reason: "unauthorized" }, req, id);
  }

  // 2. ET window. A tick outside it is a no-op, not a failure — 200 so the
  //    Vercel cron log stays green and a real failure stands out.
  const decision = dispatchDecision(job, now);
  if (!decision.allowed) {
    return json(200, { ...named, reason: decision.reason }, req, id);
  }

  // 3. Token. Also loud: never a 200 that looks like a no-op.
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    console.error("[cron] GITHUB_DISPATCH_TOKEN is not configured");
    return json(
      500,
      { ...named, reason: "GITHUB_DISPATCH_TOKEN not configured" },
      req,
      id,
    );
  }

  // 4. Has this window already been built? Vercel firing twice, or GitHub's
  //    backup cron having got there first, must not spend a second sweep.
  try {
    const dupe = suppressedBy(await recentRuns(job, now, token), job, now);
    if (dupe !== null) {
      return json(200, { ...named, reason: `already_ran:${dupe}` }, req, id);
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error(`[cron] duplicate probe failed for ${id}: ${msg}`);
    if (!DISPATCH_WHEN_PROBE_FAILS) {
      return json(200, { ...named, reason: `probe_failed:${msg}` }, req, id);
    }
  }

  // 5. Dispatch.
  const resp = await fetch(
    `${GITHUB_API}/repos/${GITHUB_REPO}/actions/workflows/${job.workflow}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(token), "Content-Type": "application/json" },
      body: JSON.stringify(dispatchBody(job)),
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    },
  );
  if (resp.status !== 204 && resp.status !== 200) {
    // A 404 here means bad token permissions or a missing workflow on `main`,
    // NOT a wrong URL: GitHub hides private repos from under-scoped tokens.
    const detail = (await resp.text().catch(() => "")).slice(0, 200);
    return json(
      502,
      {
        ...named,
        reason: `github dispatch failed: ${detail || resp.statusText}`,
        githubStatus: resp.status,
      },
      req,
      id,
    );
  }
  return json(
    200,
    {
      dispatched: true,
      workflow: job.workflow,
      slot,
      reason: "dispatched",
      githubStatus: resp.status,
    },
    req,
    id,
  );
}
