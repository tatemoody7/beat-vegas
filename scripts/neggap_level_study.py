#!/usr/bin/env python
"""H-NEGGAP-L -- the negative gap band under the H-INSEASON arms' corrected level.

A REPORT, NOT A BET. Registry row H-NEGGAP-L has no criterion: this prints the
count of negative-gap games, the over rate among decided games and its Wilson
95% interval for the champion and for each arm, one anchor build per week,
beside the 2023-25 real-close rate (R07). Nothing is written to the database.

Inputs are stored rows only: each `cards` payload item's `gap` and `hr_line`
(basis hardrock), that build's `challenger_picks` context (`c_prior`,
`c_season`, `in_season_n`), and `games.first_half_total`. The arithmetic is in
beatvegas/backtest/neggap_level.py.

    PYTHONPATH=. python scripts/neggap_level_study.py --season 2026 --out reports/neggap_level
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent))

from residual_gate import append_step_summary, report_paths  # noqa: E402

from beatvegas.backtest import neggap_level as N  # noqa: E402
from beatvegas.db.store import session_scope, try_init_db  # noqa: E402


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", default="reports/neggap_level")
    return ap.parse_args(argv)


def load_builds(session, season: int) -> Dict[int, List[Dict[str, Any]]]:
    """{week: [build, ...]}; each build carries its items and, when the
    challenger family logged at that build, one context dict (the arms share
    c_prior / c_season / in_season_n, so any arm's row will do)."""
    cards = session.execute(
        text("SELECT week, built_at, payload FROM cards WHERE season = :s ORDER BY built_at"),
        {"s": int(season)},
    ).all()
    ctx_rows = session.execute(
        text(
            "SELECT placed_at, slot, c_prior, c_season, in_season_n FROM challenger_picks "
            "WHERE season = :s AND c_prior IS NOT NULL"
        ),
        {"s": int(season)},
    ).all()
    ctx_by_placed: Dict[str, Dict[str, Any]] = {}
    for placed_at, slot, c_prior, c_season, n in ctx_rows:
        ctx_by_placed[str(placed_at)] = {
            "slot": slot,
            "c_prior": c_prior,
            "c_season": c_season,
            "in_season_n": n,
        }
    weeks: Dict[int, List[Dict[str, Any]]] = {}
    for week, built_at, payload in cards:
        try:
            card = json.loads(payload)
        except (TypeError, ValueError):
            continue
        ctx = ctx_by_placed.get(str(built_at))
        weeks.setdefault(int(week), []).append(
            {
                "built_at": built_at,
                "slot": card.get("slot") or (ctx or {}).get("slot"),
                "items": card.get("items") or [],
                "context": ctx,
            }
        )
    return weeks


def load_finals(session, season: int) -> Dict[int, Optional[float]]:
    rows = session.execute(
        text("SELECT id, first_half_total FROM games WHERE season = :s"), {"s": int(season)}
    ).all()
    return {int(g): (None if fh is None else float(fh)) for g, fh in rows}


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[neggap_level] DB unreachable — skipped.")
        return 0
    with session_scope() as s:
        weeks = load_builds(s, args.season)
        finals = load_finals(s, args.season)
    r = N.evaluate(weeks, finals)
    r["season"] = args.season
    r["generated_at"] = datetime.now(timezone.utc).isoformat()
    md = N.render_markdown(r)
    md_path, json_path, _csv = report_paths(args.out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md)
    json_path.write_text(json.dumps(r, indent=1, default=str))
    append_step_summary(md)
    print(md)
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
