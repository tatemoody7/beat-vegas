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
import { safeEqual } from "@/lib/auth";
import { etClock12 } from "@/lib/et";
import { prisma } from "@/lib/prisma";

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

// The gauge that says the primary trigger is alive. GitHub's own crons are the
// backup, and if this route stops firing the system degrades to them invisibly
// -- or to Tate dispatching by hand, which the runs API cannot tell apart from a
// Vercel dispatch (same actor, same event; 2026-09-22). So the row records the
// last time a Vercel tick ACTED inside its window: dispatched a build, or found
// one already there. A refused tick (wrong day, outside the window) writes
// nothing -- that is the case lib/boardHealth.ts turns into a banner. One
// app_settings row per job (beatvegas/ops.py::last_dispatch_key); the value is
// naive UTC to the second, the shape every other gauge uses. Never fails the
// dispatch.
async function recordTriggerGauge(id: string, now: Date, note: string) {
  try {
    const value = now.toISOString().slice(0, 19);
    await prisma.$executeRaw`
      INSERT INTO app_settings (key, value, note, updated_at)
      VALUES (${`last_dispatch_${id}`}, ${value}, ${note}, ${now}::timestamp)
      ON CONFLICT (key) DO UPDATE
        SET value = EXCLUDED.value, note = EXCLUDED.note, updated_at = EXCLUDED.updated_at`;
  } catch (e) {
    console.error(
      "[cron] dispatch gauge not recorded:",
      String((e as Error)?.message ?? e),
    );
  }
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
  // lib/auth.ts::safeEqual, not a second hand-rolled compare. The local one
  // returned early on a length mismatch, which leaked the secret's length;
  // safeEqual hashes both sides to a fixed width first, so it does not.
  if (
    !header.startsWith("Bearer ") ||
    !(await safeEqual(header.slice(7), secret))
  ) {
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
      // The tick arrived in its window and the build exists: the trigger is
      // alive even though it dispatched nothing.
      await recordTriggerGauge(id, now, `already_ran:${dupe}`);
      return json(200, { ...named, reason: `already_ran:${dupe}` }, req, id);
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error(`[cron] duplicate probe failed for ${id}: ${msg}`);
    if (!DISPATCH_WHEN_PROBE_FAILS) {
      return json(200, { ...named, reason: `probe_failed:${msg}` }, req, id);
    }
  }

  // 5. Dispatch. Wrapped: the 8s AbortSignal.timeout throws rather than
  //    returning, so an unresponsive GitHub used to produce a framework 500
  //    that never reached the structured logger below — the one record of what
  //    this route did.
  let resp: Response;
  try {
    resp = await fetch(
      `${GITHUB_API}/repos/${GITHUB_REPO}/actions/workflows/${job.workflow}/dispatches`,
      {
        method: "POST",
        headers: { ...ghHeaders(token), "Content-Type": "application/json" },
        body: JSON.stringify(dispatchBody(job)),
        cache: "no-store",
        signal: AbortSignal.timeout(TIMEOUT_MS),
      },
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return json(
      502,
      { ...named, reason: `dispatch request failed: ${msg}` },
      req,
      id,
    );
  }
  if (resp.status === 204 || resp.status === 200) {
    await recordTriggerGauge(id, now, "dispatched");
  }
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
