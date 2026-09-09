import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CRON_JOBS,
  cronJobFor,
  dispatchBody,
  dispatchDecision,
  suppressedBy,
  windowOpenInstant,
  type RunSummary,
} from "@/lib/cronJobs";

const at = (iso: string) => new Date(iso);

describe("dispatchDecision", () => {
  it("admits the EDT afternoon tick and refuses the EST one an hour early", () => {
    // The whole reason a job carries several UTC hours: 20:00Z is 4pm in
    // summer and 3pm in winter, and at 3pm Hard Rock has not posted the
    // weeknight lines this build exists to catch.
    const job = CRON_JOBS["card-tue-pm"];
    expect(dispatchDecision(job, at("2026-09-15T20:10:00Z")).allowed).toBe(
      true,
    );
    const est = dispatchDecision(job, at("2026-11-17T20:10:00Z"));
    expect(est.allowed).toBe(false);
    expect(est.reason).toContain("before_window");
    // ... and 21:00Z carries EST.
    expect(dispatchDecision(job, at("2026-11-17T21:10:00Z")).allowed).toBe(
      true,
    );
  });

  it("refuses an afternoon tick that lands after the window", () => {
    const d = dispatchDecision(
      CRON_JOBS["card-thu-pm"],
      at("2026-09-17T21:30:00Z"), // Thu 5:30pm EDT
    );
    expect(d.allowed).toBe(false);
    expect(d.reason).toContain("after_window");
  });

  it("is inclusive at both afternoon boundaries", () => {
    const job = CRON_JOBS["card-fri-pm"];
    expect(dispatchDecision(job, at("2026-09-18T19:45:00Z")).allowed).toBe(
      true,
    ); // 3:45pm
    expect(dispatchDecision(job, at("2026-09-18T19:44:00Z")).allowed).toBe(
      false,
    );
    expect(dispatchDecision(job, at("2026-09-18T21:15:00Z")).allowed).toBe(
      true,
    ); // 5:15pm
    expect(dispatchDecision(job, at("2026-09-18T21:16:00Z")).allowed).toBe(
      false,
    );
  });

  it("refuses a job on the wrong ET weekday", () => {
    const d = dispatchDecision(
      CRON_JOBS["card-tue-pm"],
      at("2026-09-16T20:10:00Z"), // Wednesday
    );
    expect(d.allowed).toBe(false);
    expect(d.reason).toContain("wrong_day");
  });

  it("closes the Saturday window at 8:15 so the build beats the 8:50 text", () => {
    const job = CRON_JOBS["card-sat-am"];
    expect(dispatchDecision(job, at("2026-09-12T11:20:00Z")).allowed).toBe(
      true,
    ); // 7:20am
    expect(dispatchDecision(job, at("2026-09-12T12:05:00Z")).allowed).toBe(
      true,
    ); // 8:05am
    // 8:20am would leave the build racing the routine that texts the card.
    expect(dispatchDecision(job, at("2026-09-12T12:20:00Z")).allowed).toBe(
      false,
    );
  });

  it("carries the Saturday window into EST on a different UTC hour", () => {
    const job = CRON_JOBS["card-sat-am"];
    expect(dispatchDecision(job, at("2026-11-14T11:20:00Z")).allowed).toBe(
      false,
    ); // 6:20am EST
    expect(dispatchDecision(job, at("2026-11-14T12:20:00Z")).allowed).toBe(
      true,
    ); // 7:20am EST
  });

  it("lets grading run at any hour on any day", () => {
    const job = CRON_JOBS["grade"];
    expect(dispatchDecision(job, at("2026-12-25T10:59:00Z")).allowed).toBe(
      true,
    );
    expect(dispatchDecision(job, at("2026-06-03T04:00:00Z")).allowed).toBe(
      true,
    );
  });
});

describe("dispatchBody", () => {
  it("omits inputs entirely for a workflow that declares none", () => {
    // grade.yml has `workflow_dispatch:` with no inputs; GitHub answers 422
    // "Unexpected inputs provided" if any are sent.
    const body = dispatchBody(CRON_JOBS["grade"]);
    expect("inputs" in body).toBe(false);
    expect(body.ref).toBe("main");
  });

  it("sends the slot for a card build", () => {
    expect(dispatchBody(CRON_JOBS["card-sat-am"]).inputs).toEqual({
      slot: "sat_am",
    });
  });
});

describe("windowOpenInstant", () => {
  it("is the same ET wall clock in both DST regimes", () => {
    const job = CRON_JOBS["card-sat-am"];
    // 7:40am EDT and 7:40am EST are an hour apart in UTC; both windows opened
    // at 7:00am ET.
    expect(
      windowOpenInstant(job, at("2026-09-12T11:40:00Z")).toISOString(),
    ).toBe("2026-09-12T11:00:00.000Z");
    expect(
      windowOpenInstant(job, at("2026-11-14T12:40:00Z")).toISOString(),
    ).toBe("2026-11-14T12:00:00.000Z");
  });
});

describe("suppressedBy", () => {
  const job = CRON_JOBS["card-sat-am"];
  const now = at("2026-11-14T12:40:00Z"); // Sat 7:40am EST, window opened 7:00
  const run = (over: Partial<RunSummary>): RunSummary => ({
    id: 1,
    event: "schedule",
    created_at: "2026-11-14T12:10:00Z",
    conclusion: "success",
    ...over,
  });

  it("does not suppress when nothing has run", () => {
    expect(suppressedBy([], job, now)).toBeNull();
  });

  it("suppresses on a dispatched run inside the window", () => {
    expect(
      suppressedBy(
        [
          run({
            event: "workflow_dispatch",
            created_at: "2026-11-14T12:20:00Z",
          }),
        ],
        job,
        now,
      ),
    ).toContain("workflow_dispatch");
  });

  it("ignores a SCHEDULED run that fired outside the build gate", () => {
    // 12:10Z is 7:10am EST — inside our dispatch window, outside ci.py's
    // 7:45–9:15 gate, so that run resolved to slot=skip and built NOTHING.
    // Counting it would silently kill the Saturday card all winter.
    expect(
      suppressedBy([run({ created_at: "2026-11-14T12:10:00Z" })], job, now),
    ).toBeNull();
  });

  it("suppresses on a scheduled run that fired inside the gate", () => {
    // 13:05Z = 8:05am EST: that one really did build.
    const later = at("2026-11-14T13:10:00Z");
    expect(
      suppressedBy([run({ created_at: "2026-11-14T13:05:00Z" })], job, later),
    ).toContain("schedule");
  });

  it("ignores runs created before the window opened", () => {
    expect(
      suppressedBy(
        [
          run({
            event: "workflow_dispatch",
            created_at: "2026-11-14T02:00:00Z",
          }),
        ],
        job,
        now,
      ),
    ).toBeNull();
  });

  it("lets a failed run be retried", () => {
    for (const conclusion of ["failure", "cancelled", "timed_out"]) {
      expect(
        suppressedBy(
          [
            run({
              event: "workflow_dispatch",
              created_at: "2026-11-14T12:20:00Z",
              conclusion,
            }),
          ],
          job,
          now,
        ),
      ).toBeNull();
    }
  });

  it("counts any run of a gate-less workflow", () => {
    const g = CRON_JOBS["grade"];
    const gnow = at("2026-11-14T12:40:00Z");
    expect(
      suppressedBy(
        [run({ created_at: "2026-11-14T10:30:00Z", conclusion: null })],
        g,
        gnow,
      ),
    ).toContain("schedule");
  });
});

describe("vercel.json stays in lock-step with the table", () => {
  const crons = JSON.parse(
    readFileSync(join(__dirname, "..", "vercel.json"), "utf8"),
  ).crons as { path: string; schedule: string }[];

  it("points every entry at a real job, and gives every job an entry", () => {
    const ids = new Set<string>();
    for (const c of crons) {
      const m = /^\/api\/cron\/([a-z0-9-]+)$/.exec(c.path);
      expect(m, `bad path ${c.path}`).not.toBeNull();
      const id = m![1];
      expect(cronJobFor(id), `unknown job ${id}`).not.toBeNull();
      ids.add(id);
    }
    expect(ids).toEqual(new Set(Object.keys(CRON_JOBS)));
  });

  it("uses a literal minute and hour in every schedule", () => {
    // Vercel Hobby allows at most one run per day per entry; anything more
    // frequent fails the DEPLOYMENT, which would silently revert the site to
    // the last good build.
    for (const c of crons) {
      const [minute, hour] = c.schedule.split(" ");
      expect(minute, c.schedule).toMatch(/^\d+$/);
      expect(hour, c.schedule).toMatch(/^\d+$/);
    }
  });

  it("gives every windowed job a fully-landing entry in BOTH DST regimes", () => {
    // Hobby fires anywhere in the hour after the scheduled minute, so an entry
    // only counts if the whole 0-59 minute band lands inside the window. This
    // is the test that catches "we picked the wrong UTC hour".
    const july = "2026-07";
    const december = "2026-12";
    const dayOf: Record<string, Record<string, string>> = {
      // A date in each month matching the cron's weekday.
      "2": { [july]: "2026-07-14", [december]: "2026-12-15" },
      "4": { [july]: "2026-07-16", [december]: "2026-12-17" },
      "5": { [july]: "2026-07-17", [december]: "2026-12-18" },
      "6": { [july]: "2026-07-18", [december]: "2026-12-19" },
    };
    for (const [id, job] of Object.entries(CRON_JOBS)) {
      if (job.days === null) continue;
      for (const month of [july, december]) {
        const landing = crons
          .filter((c) => c.path.endsWith(id))
          .filter((c) => {
            const [minute, hour, , , dow] = c.schedule.split(" ");
            const date = dayOf[dow]?.[month];
            if (!date) return false;
            const h = hour.padStart(2, "0");
            const first = at(`${date}T${h}:${minute.padStart(2, "0")}:00Z`);
            const last = new Date(first.getTime() + 59 * 60_000);
            return (
              dispatchDecision(job, first).allowed &&
              dispatchDecision(job, last).allowed
            );
          });
        expect(
          landing.length,
          `${id} has no entry that always lands in ${month}`,
        ).toBeGreaterThanOrEqual(1);
      }
    }
  });
});
