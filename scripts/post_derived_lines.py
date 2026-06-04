#!/usr/bin/env python
"""Write our derived-1H numbers for the posted lines to the board (Neon).

Display-only: for each posted full-game line, compute our spread-adjusted derived
1H total and store a `predictions` row with model_version="derived_lines" and all
MODEL fields NULL (no under_score, no bv_line, no gap). The Opportunities board
renders these as cards labeled "DERIVED — no model pick". Real in-season scoring
(gbm_v1, newer created_at) auto-supersedes them per the season-scoped board query.

Runs in the cloud (GitHub Actions) against Neon — the Mac can't reach Neon on the
campus network. Idempotent: replaces prior derived_lines rows for the season.

    python scripts/post_derived_lines.py --season 2026 --week 1
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Dict, List, Optional

from beatvegas.db.models import Game, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.match import match_event
from beatvegas.etl.proxy_line import fh_share, proxy_total
from beatvegas.season import current_season
from beatvegas.sources.cfbd import CFBDClient
from beatvegas.sources.cfbd_lines import full_game_rows as cfbd_full_game_rows
from beatvegas.sources.draftkings import DraftKingsClient, normalize_full_game

MODEL_VERSION = "derived_lines"


def fetch(source: str, season: int):
    """(rows, source_used) — DK first, CFBD fallback (mirrors poll_full_game)."""
    if source in ("dk", "auto"):
        rows = normalize_full_game(DraftKingsClient().fetch_ncaaf())
        if rows or source == "dk":
            return rows, "dk"
    return cfbd_full_game_rows(CFBDClient(), season), "cfbd"


def build_prediction_rows(
    fetched: List[Dict], gmeta: Dict[int, Dict], week: Optional[int]
) -> List[Dict]:
    """Pure: map posted full-game rows -> derived-1H prediction-row dicts.

    `gmeta`: game_id -> {week, home, away}. `games` list for name matching is
    derived from gmeta. Returns dicts ready for the Prediction model (model fields
    omitted = NULL), ranked by lowest derived 1H. Unit-tested without a DB."""
    games = [
        {"id": gid, "home_team": m["home"], "away_team": m["away"], "start_date": None}
        for gid, m in gmeta.items()
    ]
    out: List[Dict] = []
    for r in fetched:
        gid = r.get("game_id")
        if gid is None:
            gid, _ = match_event(r["home_team"], r["away_team"], r["commence_time"], games)
        if gid is None or gid not in gmeta:
            continue
        if week is not None and gmeta[gid]["week"] != week:
            continue
        total, spread = r["line"], r.get("spread")
        derived = proxy_total(total, spread=spread)
        out.append(
            {
                "game_id": gid,
                "line_used": derived,
                "factors_json": json.dumps(
                    {
                        "line": derived,
                        "line_kind": "derived_fg",
                        "full_game_total": total,
                        "spread": spread,
                        "fh_share": round(fh_share(spread), 3),
                    }
                ),
            }
        )
    out.sort(key=lambda d: d["line_used"])  # lowest derived 1H first
    for i, d in enumerate(out, start=1):
        d["rank"] = i
    return out


def write_derived_rows(session, fetched, gmeta, week, now) -> int:
    """Build derived-1H rows and persist them, replacing any prior derived_lines
    rows for the season's games (idempotent). Returns the number written."""
    rows = build_prediction_rows(fetched, gmeta, week)

    season_ids = list(gmeta.keys())
    if season_ids:
        (
            session.query(Prediction)
            .filter(
                Prediction.model_version == MODEL_VERSION, Prediction.game_id.in_(season_ids)
            )
            .delete(synchronize_session=False)
        )
    for d in rows:
        session.add(
            Prediction(
                game_id=d["game_id"],
                model_version=MODEL_VERSION,
                line_used=d["line_used"],
                rank=d["rank"],
                factors_json=d["factors_json"],
                created_at=now,
            )
        )
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=current_season())
    ap.add_argument("--week", type=int, help="filter to one week (e.g. 1)")
    ap.add_argument("--source", choices=("dk", "cfbd", "auto"), default="auto")
    args = ap.parse_args()

    if not try_init_db():
        return

    fetched, source = fetch(args.source, args.season)
    now = datetime.utcnow()

    with session_scope() as s:
        gmeta = {
            g.id: {"week": g.week, "home": g.home_team, "away": g.away_team}
            for g in s.query(Game).filter(Game.season == args.season).all()
        }
        n = write_derived_rows(s, fetched, gmeta, args.week, now)

    print(
        f"source={source} season={args.season} "
        f"week={args.week if args.week is not None else 'all'} "
        f"derived_rows_written={n}"
    )


if __name__ == "__main__":
    main()
