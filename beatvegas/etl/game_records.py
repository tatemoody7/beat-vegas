"""Immutable per-game snapshots — our own model-shaped record (plan Phase 0).

`snapshot_slate` freezes one GameRecord per game from a scored slate (the
leak-free feature vector + the line + our as-of-then bv_line/gap). It's
idempotent per (game, model_version): the first pre-kickoff capture stands, so
the record is never silently overwritten. `grade_records` fills the real 1H
result + under/over/push outcome after the game — the only post-kickoff write.

The cumulative store feeds the Research records grid, the credibility ledger,
and bv_line recalibration; a re-scoreable view re-runs the current model over
`features_json` without mutating these frozen rows.
"""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

import pandas as pd

from ..db.models import Game, GameRecord
from ..grading import trusted_first_half_total
from .features import FEATURE_COLS


def _clean(v) -> Optional[float]:
    return None if v is None or pd.isna(v) else float(v)


def outcome_of(first_half_total, line) -> Tuple[Optional[bool], Optional[str]]:
    """(under_hit, outcome) for a 1H result vs a line. Push = no bet (None hit)."""
    if first_half_total is None or line is None:
        return (None, None)
    if first_half_total < line:
        return (True, "under")
    if first_half_total > line:
        return (False, "over")
    return (None, "push")


def record_fields(
    row: pd.Series, model_version: str, feature_cols: List[str] = FEATURE_COLS
) -> dict:
    """The frozen GameRecord fields for one scored game (excludes captured_at).

    `engine` is the PER-ROW 1H engine score_slate stamped on the row (the same
    value that reaches factors_json) — under the residual engine one slate can
    carry both, because a row with no real posted 1H line falls back to the
    incumbent. It is an added dimension alongside `model_version`, not a
    replacement; a slate scored before the column existed freezes it NULL.
    """
    feats = {c: _clean(row.get(c)) for c in feature_cols}
    us = row.get("under_score")
    eng = row.get("engine")
    return {
        "game_id": int(row["id"]),
        "season": int(row["season"]),
        "week": int(row["week"]),
        "model_version": model_version,
        "engine": eng if isinstance(eng, str) else None,
        "features_json": json.dumps(feats),
        "line": _clean(row.get("line")),
        "line_kind": row.get("line_kind") if isinstance(row.get("line_kind"), str) else None,
        "bv_line": _clean(row.get("bv_line")),
        "bv_gap": _clean(row.get("bv_gap")),
        "bv_gap_z": _clean(row.get("bv_gap_z")),
        "under_score": None if us is None or pd.isna(us) else int(us),
    }


def snapshot_slate(
    session, scored: pd.DataFrame, model_version: str, now, feature_cols=FEATURE_COLS
) -> int:
    """Freeze a GameRecord per game; skip games already snapshotted (immutable)."""
    existing = {
        gid
        for (gid,) in session.query(GameRecord.game_id)
        .filter(GameRecord.model_version == model_version)
        .all()
    }
    n = 0
    for _, r in scored.iterrows():
        if int(r["id"]) in existing:
            continue
        session.add(GameRecord(captured_at=now, **record_fields(r, model_version, feature_cols)))
        n += 1
    return n


def grade_records(session, now) -> int:
    """Fill the real 1H result + outcome for ungraded records whose game is final.

    Grades through `grading.trusted_first_half_total`, exactly as every other
    grader does (picks.grade_pick, grade.grade_market/grade_model, the two
    post-mortem frames, model.residual). A LINE-SCORE 0 against a non-zero final
    is the known false-zero corruption, and booking it here would fabricate an
    UNDER win into the records grid, the credibility ledger and bv_line
    recalibration. An untrusted row stays ungraded so a later PBP repair can
    still grade it.
    """
    recs = session.query(GameRecord).filter(GameRecord.graded_at.is_(None)).all()
    n = 0
    for rec in recs:
        g = session.get(Game, rec.game_id)
        if g is None:
            continue
        actual = trusted_first_half_total(
            g.first_half_total, g.home_points, g.away_points, g.first_half_source
        )
        if actual is None:
            continue
        hit, oc = outcome_of(actual, rec.line)
        # round, not truncate: 13.6 is 14 points, not 13.
        rec.first_half_total = int(round(actual))
        rec.under_hit = hit
        rec.outcome = oc
        rec.graded_at = now
        n += 1
    return n
