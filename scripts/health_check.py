#!/usr/bin/env python
"""The last step of every scheduled Neon-writing job: did this run leave behind
what it was for? (beatvegas/health.py, docs/HEALTH.md)

    python scripts/health_check.py --job card  --sweep-status "$RUNNER_TEMP/sweep_status.json"
    python scripts/health_check.py --job grade
    python scripts/health_check.py --job sunday
    python scripts/health_check.py --job lines_watch --close-status "$RUNNER_TEMP/close_status.json"

Reads the run's facts from the environment the workflow passes through `env:`
(never inlined into bash): SKIPPED, RUN_STARTED_AT (ISO UTC, the gate/probe
step's `started=` output), SEASON / WEEK ('' = none), SLOT, MARKET, every
OUTCOME_<step> (GitHub's step outcome), NEED_CAPTURE / NEED_SCORE, plus
GITHUB_RUN_ID and GITHUB_EVENT_NAME for the note. Then:

  - SKIPPED=true        -> "skipped run, no verdict", exit 0, writes nothing
                           (a gate-skip tick is not a run of the job).
  - DB unreachable      -> exit 0 outside GitHub Actions (try_init_db re-raises
                           inside GHA, where unreachable is a real failure).
  - otherwise           -> evaluate the contract, write the verdict + note to the
                           `last_health_<job>` gauge (ops.health_key), print one
                           line per check, a ::warning:: per miss (::error:: when
                           the verdict is failed), append `HEALTH: <verdict>
                           <note>` to $GITHUB_STEP_SUMMARY, and exit 1 on a
                           `failed` verdict (so GitHub's failed-run email goes
                           out) unless --fail-on never.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

# Run as `python scripts/health_check.py` (the workflows do), sys.path holds
# scripts/ and not the repo root; put the root first so the package this
# checkout carries is the one imported, even where an editable install points at
# another checkout (a worktree).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beatvegas import health  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402
from beatvegas.ops import health_key, record_gauge  # noqa: E402

# When the workflow did not hand over RUN_STARTED_AT (a local run), judge the
# run against this much history and say so.
DEFAULT_LOOKBACK_HOURS = 2.0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--job", required=True, choices=sorted(health.CONTRACTS))
    ap.add_argument(
        "--fail-on",
        choices=("failed", "never"),
        default="failed",
        help="exit 1 on a `failed` verdict (default) or never",
    )
    ap.add_argument("--sweep-status", metavar="FILE", help="card.yml's 1H sweep status file")
    ap.add_argument(
        "--close-status", metavar="FILE", help="lines_watch.yml's close poll status file"
    )
    return ap.parse_args(argv)


def parse_utc(raw: Optional[str]) -> Optional[datetime]:
    """'2026-09-23T14:05:00Z' (date -u +%FT%TZ) or any ISO form -> naive UTC."""
    if not raw:
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is not None:
        d = (d - d.utcoffset()).replace(tzinfo=None)
    return d


def _int_or_none(raw: Optional[str]) -> Optional[int]:
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def load_status_files(paths: Mapping[str, Optional[str]]) -> Dict[str, dict]:
    """{name: parsed JSON} for the status files that exist and parse. A path
    given but missing is simply absent -- the check decides what that means."""
    out: Dict[str, dict] = {}
    for name, path in paths.items():
        if not path:
            continue
        p = Path(path)
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            out[name] = data
    return out


def ctx_from_env(
    job: str,
    env: Mapping[str, str],
    *,
    session,
    now: Optional[datetime] = None,
    status_files: Optional[Dict[str, dict]] = None,
) -> Tuple[health.Ctx, List[str]]:
    """Build the Ctx the checks read. Returns (ctx, notices): a notice is a line
    to print about a value that was missing or malformed."""
    notices: List[str] = []
    now = now or datetime.utcnow()
    started = parse_utc(env.get("RUN_STARTED_AT"))
    if started is None:
        started = now - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
        notices.append(
            f"RUN_STARTED_AT missing or unparseable ({env.get('RUN_STARTED_AT')!r}); "
            f"judging the last {DEFAULT_LOOKBACK_HOURS:g} h"
        )
    outcomes = {
        k[len("OUTCOME_") :].lower(): v for k, v in env.items() if k.startswith("OUTCOME_") and v
    }
    return (
        health.Ctx(
            session=session,
            now=now,
            job=job,
            run_started_at=started,
            season=_int_or_none(env.get("SEASON")),
            week=_int_or_none(env.get("WEEK")),
            slot=(env.get("SLOT") or None),
            market=(env.get("MARKET") or None),
            outcomes=outcomes,
            status_files=dict(status_files or {}),
            env=dict(env),
        ),
        notices,
    )


def step_summary(line: str) -> None:
    """Same shape as beatvegas/ci.py::warn -- one line on the run summary."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    job = args.job
    if env.get("SKIPPED") == "true":
        print(f"[health:{job}] skipped run, no verdict")
        return 0
    if not try_init_db():
        print(f"[health:{job}] DB unreachable — no verdict written.")
        return 0
    status_files = load_status_files({"sweep": args.sweep_status, "close": args.close_status})
    contract = health.CONTRACTS[job]
    with session_scope() as s:
        ctx, notices = ctx_from_env(job, env, session=s, status_files=status_files)
        for n in notices:
            print(f"::warning::[health:{job}] {n}")
        verdict, results = health.evaluate(contract, ctx)
        note = health.verdict_note(job, ctx, results)
        written = record_gauge(health_key(job), verdict, note, session=s)
    for check, res in results:
        mark = "ok  " if res.ok else "MISS"
        print(f"[health:{job}] {mark} {check.id} ({check.severity}): {res.detail}")
        if not res.ok:
            level = "error" if verdict == "failed" and check.severity == "failed" else "warning"
            print(f"::{level}::{check.id}: {res.detail}")
    print(
        f"[health:{job}] verdict={verdict} gauge={'written' if written else 'NOT written'} {note}"
    )
    step_summary(f"HEALTH: {verdict} {note}")
    if verdict == "failed" and args.fail_on == "failed":
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(parse_args(argv), os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
