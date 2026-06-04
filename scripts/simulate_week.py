#!/usr/bin/env python
"""Dry-run the whole system as if it were a live game week — locally, isolated.

Spins up a throwaway local Postgres (scripts/pg_sim.py), replays a real past week,
and builds a PRE-GAME slate: real games + lines + model picks, but NO results and
nothing graded — exactly the board you'd face on game day before kickoff. You then
place your own picks in the app (My Picks) and reveal the outcomes with --grade.
Writes ONLY to the local sandbox, never Neon. The "alert" is printed, never sent.

    python scripts/simulate_week.py                       # build 2025 wk8 pre-game
    python scripts/simulate_week.py --season 2025 --week 1 # cold-start rehearsal
    python scripts/simulate_week.py --grade                # reveal: grade vs finals

The week defaults to 8 (a full model board). A literal Week 1 is a cold start: the
model needs >= 2 prior games that season, so wk1 shows only DERIVED reference cards.
"""

from __future__ import annotations

import argparse
import os

import pg_sim


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument(
        "--week", type=int, default=8, help="default 8 (full model board); use 1 for cold-start"
    )
    ap.add_argument(
        "--limit", type=int, default=12, help="max games to include (cheapest-total first); 0 = all"
    )
    ap.add_argument(
        "--grade",
        action="store_true",
        help="REVEAL: grade the market + your placed picks vs final "
        "scores (run after you've made picks; no rebuild)",
    )
    args = ap.parse_args()

    # Bring up the local sandbox and point THIS process at it before any
    # beatvegas import resolves the DB engine.
    uri = pg_sim.start()
    os.environ.pop("BEATVEGAS_DB", None)
    os.environ["DATABASE_URL"] = uri

    from beatvegas.pipeline import run_pipeline

    if args.grade:
        res = run_pipeline("sim", args.season, args.week, mode="replay", action="grade")
        print(
            f"[reveal] market={res['market']} model={res['model']} "
            f"your_picks={res['your_picks']} — check the Ledger + My Picks."
        )
        return

    print(f"[sim] local Postgres up: {uri}")
    res = run_pipeline(
        "sim", args.season, args.week, mode="replay", notify="print", limit=(args.limit or None)
    )

    print("[sim] cloned input rows: " + ", ".join(f"{k}={v}" for k, v in res["cloned"].items()))
    print(
        f"[sim] PRE-GAME slate: {res['games']} games | {res['model_preds']} "
        f"model picks | {res['derived_preds']} derived reference lines | "
        f"no results yet"
    )

    if res["model_preds"] == 0:
        print(
            "\n*** COLD START *** — no model picks this week (needs >= 2 prior "
            "games that season). Board shows DERIVED reference cards only. Use a "
            "later week (e.g. --week 8) for the full model board.\n"
        )

    print("\nPlay it like a real week:")
    print(f'  1) point web/.env at the sim:  DATABASE_URL="{uri}"')
    print("  2) cd web && npm run dev   ->   open http://localhost:3000")
    print("  3) browse the board, place your picks in 'My Picks'")
    print("  4) when ready to see how you did:  python scripts/simulate_week.py --grade")
    print("Stop the sandbox when done:  python scripts/pg_sim.py stop")


if __name__ == "__main__":
    main()
