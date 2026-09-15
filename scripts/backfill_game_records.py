#!/usr/bin/env python
"""Freeze GameRecords for a week that was scored AFTER it was played.

`weekly_update.py --no-snapshot` (rescore.yml) deliberately skips
`snapshot_slate`: a GameRecord means "frozen before kickoff", and a retro
re-score is not that. 2026 week 1 was re-scored on 2026-09-10 (the week had
kicked off before the season's first Sunday build), so its 50 predictions never
reached `game_records` and the factor ledger / records grid carry no week-1
model row.

This writes those rows from the `predictions` table with `captured_at` = the
prediction's own `created_at`. For a retro week that timestamp is AFTER the
game's `start_date`, which is exactly how the row declares itself: anything
reading `game_records` can (and the records grid does) split pre-kickoff from
scored-after-the-game on that comparison. Nothing is invented — line, kind, our
number, gap and score are the stored prediction's. Rows already frozen for the
model version are left alone. `--write` grades the new rows the same way
scripts/grade_records.py does; without it, report only.

    PYTHONPATH=. python scripts/backfill_game_records.py --season 2026 --week 1
    PYTHONPATH=. python scripts/backfill_game_records.py --season 2026 --week 1 --write
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from typing import Dict, List, Optional

from beatvegas.db.models import Game, GameRecord, Prediction
from beatvegas.db.store import resync_table_sequence, session_scope, try_init_db
from beatvegas.etl.features import FEATURE_COLS
from beatvegas.etl.game_records import grade_records
from beatvegas.model.score import MODEL_VERSION


def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _factors(p: Prediction) -> Dict:
    try:
        f = json.loads(p.factors_json) if p.factors_json else {}
    except (TypeError, ValueError):
        f = {}
    return f if isinstance(f, dict) else {}


def record_from_prediction(g: Game, p: Prediction) -> GameRecord:
    f = _factors(p)
    feats = {c: _num(f.get(c)) for c in FEATURE_COLS if c in f}
    gap = _num(p.bv_gap)
    sigma = _num(p.bv_sigma)
    lk = f.get("line_kind")
    eng = f.get("engine")
    return GameRecord(
        game_id=g.id,
        season=g.season,
        week=g.week,
        captured_at=p.created_at,  # after kickoff on a retro week: self-declaring
        model_version=p.model_version,
        engine=eng if isinstance(eng, str) else None,
        features_json=json.dumps(feats),
        line=_num(p.line_used),
        line_kind=lk if isinstance(lk, str) else None,
        bv_line=_num(p.bv_line),
        bv_gap=gap,
        bv_gap_z=(round(gap / sigma, 4) if gap is not None and sigma else None),
        under_score=None if p.under_score is None else int(p.under_score),
    )


def backfill_records(
    session, season: int, week: int, model_version: str = MODEL_VERSION
) -> List[GameRecord]:
    """The GameRecords a week's stored predictions would freeze — NOT added.
    Games that already carry a record for `model_version` are skipped."""
    existing = {
        gid
        for (gid,) in session.query(GameRecord.game_id)
        .filter(GameRecord.season == season, GameRecord.week == week)
        .filter(GameRecord.model_version == model_version)
        .all()
    }
    rows = (
        session.query(Game, Prediction)
        .join(Prediction, Prediction.game_id == Game.id)
        .filter(Game.season == season, Game.week == week)
        .filter(Prediction.model_version == model_version)
        .order_by(Prediction.created_at, Prediction.id)
        .all()
    )
    out: Dict[int, GameRecord] = {}
    for g, p in rows:
        if g.id in existing or p.bv_line is None:
            continue
        out[g.id] = record_from_prediction(g, p)  # newest prediction per game wins
    return list(out.values())


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--model-version", default=MODEL_VERSION)
    ap.add_argument("--write", action="store_true", help="apply; otherwise report only")
    args = ap.parse_args()
    if not try_init_db():
        print("[records] DB unreachable — skipped (no traceback).")
        return
    with session_scope() as s:
        recs = backfill_records(s, args.season, args.week, args.model_version)
        retro = 0
        for r in recs:
            g = s.get(Game, r.game_id)
            if (
                r.captured_at is not None
                and g.start_date is not None
                and r.captured_at > g.start_date
            ):
                retro += 1
        print(
            f"[records] {args.season} week {args.week}: {len(recs)} prediction(s) with no GameRecord "
            f"({retro} scored after kickoff, {len(recs) - retro} before)."
        )
        if not args.write:
            print("DRY RUN - nothing written")
            return
        resync_table_sequence(s, GameRecord.__tablename__)
        for r in recs:
            s.add(r)
        s.flush()
        n = grade_records(s, datetime.utcnow())
        print(f"[records] wrote {len(recs)} record(s); graded {n}.")


if __name__ == "__main__":
    main()
