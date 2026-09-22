#!/usr/bin/env python
"""Backfill `predictions.bv_intercept` for rows scored before the column existed.

`Prediction.bv_intercept` was added on 2026-09-21 (PR #201) so the H-INSEASON
challenger family can recover each row's RAW, pre-intercept prediction as
`bv_line - bv_intercept`. But `score_slate` writes the column only for the rows
it scores, and `store_predictions` rewrites only the TARGET WEEK -- so every
2026 row scored before the merge (weeks 1-4, 214 rows) carries NULL and would
carry it forever. Without them `challenger_picks.completed_season_rows` sees no
completed game at all: the arms log nothing, and `c_season` could only ever be
estimated from week 5 on, which is not the estimator H-INSEASON-P registered
("the season's games completed strictly before the build").

The intercept is ONE number per season by construction: `bias_corrections(train)
["global"]` with `train` = the played prior-season rows of the `min_games=0`
frame, none of which change during the season. This script recomputes it the
way `score_slate` does (beatvegas/model/score.py, the `bv_intercept` line),
refuses to write unless the value agrees with the one recorded against the live
board in docs/MODEL_LEVEL_2026.md (-1.8092) to within 0.001, and then fills
ONLY the NULL rows of the season's model predictions. `bv_line` is never
touched; the script prints its sum before and after so that is checkable.

Run it on the GitHub runner (`.github/workflows/backfill_intercept.yml`), not
on a laptop: HistGradientBoosting output is not pinned across platforms, and
the runner's pins are what wrote the rows being repaired.

    python scripts/backfill_bv_intercept.py --season 2026            # dry run
    python scripts/backfill_bv_intercept.py --season 2026 --write
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, Optional, Sequence

from sqlalchemy import func

from beatvegas.db.models import Game, Prediction
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.features import apply_min_games, build_feature_frame, training_frame
from beatvegas.model.bv_line import bias_corrections, bv_line_for_slate
from beatvegas.model.score import MODEL_VERSION

# The intercept the live board applied all season (docs/MODEL_LEVEL_2026.md,
# "2026 | 153 | 2,212 | -1.8092"). A recomputation that lands elsewhere means
# the training frame or the platform differs from the one that scored the rows,
# and the "raw" predictions recovered from it would be wrong by the difference.
RECORDED_INTERCEPT = -1.8092
TOLERANCE = 0.001


def compare_stored(recomputed: Dict[int, float], stored: Dict[int, float]) -> Dict[str, Any]:
    """recomputed - stored over the games both carry. A mean near zero with a
    tiny max says the runner reproduces the rows (same model, same intercept);
    a mean sitting at a constant offset says the intercept the rows were scored
    with differs from today's by exactly that much."""
    ids = sorted(set(recomputed) & set(stored))
    diffs = [float(recomputed[i]) - float(stored[i]) for i in ids]
    if not diffs:
        return {"n": 0}
    absd = [abs(d) for d in diffs]
    return {
        "n": len(diffs),
        "mean_signed": round(sum(diffs) / len(diffs), 4),
        "mean_abs": round(sum(absd) / len(absd), 4),
        "max_abs": round(max(absd), 4),
        "within_0_01": sum(1 for a in absd if a <= 0.01),
    }


def verify_against_stored(
    session, season: int, frame, model_version: str = MODEL_VERSION
) -> Dict[int, Dict[str, Any]]:
    """Per week: recompute `bv_line_for_slate` for the season's STORED rows on
    today's frame and compare. Week 1's features are prior-season priors only and
    never change, so week 1 must reproduce to rounding if the intercept the rows
    carry is the one this platform computes; later weeks pick up season-to-date
    feature drift and are context only."""
    df = apply_min_games(frame, 0)
    train = training_frame(df[df["season"] < int(season)])
    stored_rows = (
        session.query(Prediction.game_id, Prediction.bv_line, Game.week)
        .join(Game, Game.id == Prediction.game_id)
        .filter(
            Game.season == int(season),
            Prediction.model_version == model_version,
            Prediction.bv_line.isnot(None),
        )
        .all()
    )
    by_week: Dict[int, Dict[int, float]] = {}
    for gid, bv, wk in stored_rows:
        by_week.setdefault(int(wk), {})[int(gid)] = float(bv)
    out: Dict[int, Dict[str, Any]] = {}
    target_all = df[df["season"] == int(season)]
    for wk in sorted(by_week):
        target = target_all[target_all["id"].isin(list(by_week[wk]))]
        if target.empty:
            out[wk] = {"n": 0}
            continue
        pred = bv_line_for_slate(train, target)
        recomputed = {int(g): round(float(v), 2) for g, v in zip(target["id"], pred)}
        out[wk] = compare_stored(recomputed, by_week[wk])
    return out


def compute_intercept(season: int, frame=None) -> tuple:
    """(intercept, n_train) exactly as score_slate derives them for `season`."""
    if frame is None:
        frame = build_feature_frame(min_games=0)
    df = apply_min_games(frame, 0)
    train = training_frame(df[df["season"] < int(season)])
    c = round(float(bias_corrections(train).get("global", 0.0)), 6)
    return c, int(len(train))


def check_tolerance(c: float, recorded: float = RECORDED_INTERCEPT, tol: float = TOLERANCE) -> None:
    if abs(float(c) - float(recorded)) >= tol:
        raise SystemExit(
            f"REFUSING TO WRITE: recomputed intercept {c:+.6f} is not within {tol} of the "
            f"recorded live value {recorded:+.4f}. The training frame or platform differs "
            "from the one that scored these rows; a backfill would mis-state every raw prediction."
        )


def _season_rows(session, season: int, model_version: str):
    return (
        session.query(Prediction)
        .join(Game, Game.id == Prediction.game_id)
        .filter(Game.season == int(season), Prediction.model_version == model_version)
    )


def backfill(
    session,
    season: int,
    intercept: float,
    *,
    write: bool,
    model_version: str = MODEL_VERSION,
) -> dict:
    """Fill NULL `bv_intercept` on the season's model rows. Returns the audit numbers."""
    q = _season_rows(session, season, model_version)
    total = q.count()
    null_ids = [
        r[0] for r in q.filter(Prediction.bv_intercept.is_(None)).with_entities(Prediction.id).all()
    ]
    sum_before = float(
        q.with_entities(func.coalesce(func.sum(Prediction.bv_line), 0.0)).scalar() or 0.0
    )
    updated = 0
    if write and null_ids:
        updated = (
            session.query(Prediction)
            .filter(
                Prediction.id.in_(null_ids),
                Prediction.bv_intercept.is_(None),
                Prediction.model_version == model_version,
            )
            .update({Prediction.bv_intercept: float(intercept)}, synchronize_session=False)
        )
    sum_after = float(
        q.with_entities(func.coalesce(func.sum(Prediction.bv_line), 0.0)).scalar() or 0.0
    )
    still_null = q.filter(Prediction.bv_intercept.is_(None)).count()
    return {
        "season": int(season),
        "model_version": model_version,
        "rows_total": int(total),
        "rows_null_before": len(null_ids),
        "rows_updated": int(updated),
        "rows_null_after": int(still_null),
        "sum_bv_line_before": round(sum_before, 4),
        "sum_bv_line_after": round(sum_after, 4),
        "intercept": float(intercept),
        "write": bool(write),
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument(
        "--verify",
        action="store_true",
        help="also recompute bv_line for the season's stored rows on this platform and print "
        "the per-week difference (week 1 must reproduce; it settles which intercept the rows "
        "were scored with). Read-only.",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="apply the UPDATE; without it the script only reports what it would do",
    )
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if not try_init_db():
        print("[backfill_bv_intercept] DB unreachable — skipped.")
        return 1
    frame = build_feature_frame(min_games=0)
    c, n_train = compute_intercept(args.season, frame)
    print(f"[backfill_bv_intercept] recomputed intercept {c:+.6f} from {n_train} training rows")
    if args.verify:
        with session_scope() as s:
            per_week = verify_against_stored(s, args.season, frame)
        for wk, r in per_week.items():
            print(f"[backfill_bv_intercept] verify week {wk}: {r}")
    print(
        f"[backfill_bv_intercept] recorded live value {RECORDED_INTERCEPT:+.4f}; "
        f"difference {c - RECORDED_INTERCEPT:+.6f} (tolerance {TOLERANCE})"
    )
    check_tolerance(c)
    with session_scope() as s:
        audit = backfill(s, args.season, c, write=args.write)
    for k, v in audit.items():
        print(f"[backfill_bv_intercept] {k}={v}")
    if audit["sum_bv_line_before"] != audit["sum_bv_line_after"]:
        raise SystemExit("bv_line changed — that must never happen; investigate before re-running")
    if not args.write:
        print(
            f"[backfill_bv_intercept] DRY RUN — {audit['rows_null_before']} rows would be set to "
            f"{c:+.6f}. Re-run with --write to apply."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
