#!/usr/bin/env python
"""Hard Rock lead/lag + first-half microstructure, from the captured snapshots.

    PYTHONPATH=. python scripts/hr_lag_study.py --season 2026 --out reports/hr_lag

Reads Neon; writes a report under reports/ (gitignored); spends nothing. See
beatvegas/backtest/hr_lag.py for what each table can and cannot support.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from beatvegas.backtest import hr_lag as H
from beatvegas.db.store import session_scope, try_init_db


def load(season: int, max_week: int) -> pd.DataFrame:
    with session_scope() as s:
        rows = (
            s.execute(
                text(
                    """
            select o.game_id, g.week, g.start_date, o.captured_at, o.book, o.line,
                   o.over_price, o.under_price
            from odds_snapshots o join games g on g.id = o.game_id
            where g.season = :season and g.week <= :w and o.market = '1H_total'
            order by o.game_id, o.captured_at
            """
                ),
                {"season": season, "w": max_week},
            )
            .mappings()
            .all()
        )
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument(
        "--max-week", type=int, default=2, help="only PLAYED weeks: captures must be pre-kick"
    )
    ap.add_argument("--out", default="reports/hr_lag")
    args = ap.parse_args()
    if not try_init_db():
        print("[hr_lag] DB unreachable — skipped.")
        return
    d = H.prepare(load(args.season, args.max_week))
    pos = H.position_table(d)
    r = {
        "season": args.season,
        "weeks": f"1–{args.max_week}",
        "grain": H.grain(d),
        "position": H.position_summary(pos),
        "who_first": H.who_moves_first(d),
        "price_before_number": H.price_before_number(d),
        "dispersion": H.dispersion(d),
        "closing": H.closing_position(d),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    md = H.render_markdown(r)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(f"{args.out}_{stamp}.md", "w").write(md)
    json.dump(r, open(f"{args.out}_{stamp}.json", "w"), indent=1, default=str)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(md)
    print(md)
    print(f"wrote {args.out}_{stamp}.md")


if __name__ == "__main__":
    main()
