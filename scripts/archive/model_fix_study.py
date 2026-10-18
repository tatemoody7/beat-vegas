"""H-MODEL-FIX (docs/HYPOTHESES.md, Tate 2026-10-10): the live champion against
the same model with four fixes, once, on the runner (`study.yml`). NOT MET on
2026-10-10 (run 38070611660, docs/MODEL_FIX.md); a rerun is a second look.

    python scripts/archive/model_fix_study.py [--test-seasons 2025 2026] [--out reports/model_fix]

Each arm on its own frame (beatvegas/backtest/model_fix.py): the candidate's
frame is the harness's shared frame, so its score pool holds no bowl game; the
incumbent's scorer reads the same game ids from the live champion's frame. Grading,
the paired bootstrap and the verdict are the shared harness's
(beatvegas/backtest/harness.py), exactly as `harness_report.py` runs them:
real consensus 1H closes inside 2 h, never a proxy line.

Order: the registry row is checked before the database opens; both frames'
fingerprints are written before anything is scored. It writes no table, no
`model_runs` row, and spends no Odds API credits.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

import pandas as pd

from beatvegas.backtest import harness as H
from beatvegas.backtest import model_fix as MF
from beatvegas.backtest.reporting import append_step_summary, report_paths, utc_stamp
from beatvegas.backtest.residual_gate import GateNotEvaluable
from beatvegas.db.store import session_scope, try_init_db
from beatvegas.etl.frame_fingerprint import fingerprint_hash, write_fingerprint
from beatvegas.markets import FIRST_HALF
from beatvegas.registry import HarnessRefusal, require_runnable_row
from beatvegas.snapshots import (
    DEFAULT_DECISION_RULE,
    consensus_closes,
    decision_lines,
    hr_close_prices,
    hr_closes,
    kickoffs_for,
)

REFUSED = 2
FAR_FROM_CLOSE_PTS = 6.0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--test-seasons", type=int, nargs="+", default=[2025, 2026])
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="report path prefix (default reports/model_fix)")
    return ap.parse_args(argv)


def extras(per_game: pd.DataFrame, legacy: pd.DataFrame) -> str:
    """The row's reported-never-gated readings, as markdown."""
    inc, cand = f"pred_{H.INCUMBENT_NAME}", f"pred_{MF.CANDIDATE_NAME}"
    df = per_game.copy()
    df = df[df["actual"].notna()]
    proj = legacy.drop_duplicates("id").set_index("id")["proj_1h_total"]
    df["proj_1h_total"] = df["game_id"].map(proj)
    lines: List[str] = ["", "## H-MODEL-FIX readings (reported, never gated)", ""]

    lines += ["### Accuracy and bias by season", ""]
    lines += [
        "| season | n | MAE incumbent | MAE fix | bias incumbent | bias fix |",
        "|---|---|---|---|---|---|",
    ]
    for s, g in df.groupby("season"):
        e_i, e_c = g[inc] - g["actual"], g[cand] - g["actual"]
        lines.append(
            f"| {int(s)} | {len(g)} | {e_i.abs().mean():.2f} | {e_c.abs().mean():.2f} | "
            f"{e_i.mean():+.2f} | {e_c.mean():+.2f} |"
        )

    lines += ["", "### By the raw season-to-date projection (`proj_1h_total`, pre-fix frame)", ""]
    lines += [
        "| decile | proj range | n | MAE incumbent | MAE fix | bias incumbent | bias fix |",
        "|---|---|---|---|---|---|---|",
    ]
    known = df[df["proj_1h_total"].notna()].copy()
    if len(known) >= 10:
        known["decile"] = pd.qcut(known["proj_1h_total"], 10, labels=False, duplicates="drop")
        for d, g in known.groupby("decile"):
            e_i, e_c = g[inc] - g["actual"], g[cand] - g["actual"]
            lines.append(
                f"| {int(d) + 1} | {g['proj_1h_total'].min():.1f}-{g['proj_1h_total'].max():.1f} | "
                f"{len(g)} | {e_i.abs().mean():.2f} | {e_c.abs().mean():.2f} | "
                f"{e_i.mean():+.2f} | {e_c.mean():+.2f} |"
            )

    if "close" in df.columns:
        graded = df[df["close"].notna()]
        far_i = int(((graded[inc] - graded["close"]).abs() > FAR_FROM_CLOSE_PTS).sum())
        far_c = int(((graded[cand] - graded["close"]).abs() > FAR_FROM_CLOSE_PTS).sum())
        lines += [
            "",
            f"### Games more than {FAR_FROM_CLOSE_PTS:g} points from the consensus close",
            "",
            f"Incumbent {far_i} of {len(graded)}; fix {far_c} of {len(graded)}.",
        ]

    wk6 = df[(df["season"] == 2026) & (df["week"] == 6)]
    if len(wk6):
        lines += ["", "### Week 6 of 2026, side by side", ""]
        lines += ["| game | incumbent | fix | close | actual |", "|---|---|---|---|---|"]
        for _, r in wk6.sort_values(inc, ascending=False).iterrows():
            close = r.get("close")
            lines.append(
                f"| {r.get('away_team')} @ {r.get('home_team')} | {r[inc]:.1f} | {r[cand]:.1f} | "
                f"{'' if pd.isna(close) else f'{close:g}'} | {r['actual']:g} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    # 1. registry first, no database yet
    try:
        row = require_runnable_row(MF.ROW_ID)
    except (HarnessRefusal, ValueError) as e:
        print(f"::error::MODEL FIX STUDY REFUSED: {e}", file=sys.stderr)
        append_step_summary(f"**MODEL FIX STUDY REFUSED: {e}**")
        return REFUSED

    # 2. database, then both frames, fingerprinted before anything is scored
    if not try_init_db():
        print("[model-fix] database unreachable; nothing computed", file=sys.stderr)
        return 0
    out = args.out or "reports/model_fix"
    stamp = utc_stamp()
    md_path, _json, _csv = report_paths(out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    legacy = MF.incumbent_frame()
    fp_legacy = write_fingerprint(legacy, md_path.with_name(md_path.stem + "_frame_incumbent.json"))
    fixed = MF.candidate_frame()
    fp_path = md_path.with_name(md_path.stem + "_frame_candidate.json")
    fp = write_fingerprint(fixed, fp_path)
    fp["path"] = str(fp_path)
    fp["source"] = {
        "snapshot": None,
        "build": {"candidate": "model_fix", "min_season": MF.CANDIDATE_FLOOR},
    }
    print(
        f"[model-fix] incumbent frame rows={fp_legacy['rows']} candidate frame rows={fp['rows']} "
        f"sklearn={fp['sklearn']}"
    )

    spec = H.HarnessSpec(
        row_id=row.id,
        arms=(
            H.Arm(H.INCUMBENT_NAME, MF.incumbent_scorer(legacy), is_incumbent=True),
            H.Arm(MF.CANDIDATE_NAME, MF.candidate_scorer),
        ),
        test_seasons=tuple(args.test_seasons),
        min_games_train=0,
        min_games_score=0,
        n_boot=args.n_boot,
        seed=args.seed,
        criterion=MF.criterion,
        frame_min_season=MF.CANDIDATE_FLOOR,
    )

    # 3. real closes for the test seasons' played games (the harness_report recipe)
    test_rows = fixed[fixed["season"].isin(list(spec.test_seasons))]
    ids = [int(g) for g in test_rows.loc[test_rows["first_half_total"].notna(), "id"].tolist()]
    with session_scope() as session:
        kicks = kickoffs_for(session, ids)
        grading = H.Grading(
            closes=consensus_closes(session, ids, kicks, market=FIRST_HALF),
            hr_closes=hr_closes(session, ids, kicks, market=FIRST_HALF),
            hr_prices=hr_close_prices(session, ids, kicks, market=FIRST_HALF, side=spec.side),
            decision_lines=decision_lines(session, ids, kicks, rule=DEFAULT_DECISION_RULE),
            decision_rule=DEFAULT_DECISION_RULE,
            market=FIRST_HALF,
        )
    print(f"[model-fix] real closes {len(grading.closes)} over {len(ids)} played test-season games")

    # 4. measure, once
    try:
        result = H.run(fixed, grading, spec, row, fp)
    except GateNotEvaluable as e:
        md_path.write_text(f"# {row.id}: NOT EVALUABLE\n\n`{e}`\n", encoding="utf-8")
        append_step_summary(f"{row.id}: NOT EVALUABLE ({e})")
        return 0
    except HarnessRefusal as e:
        print(f"::error::MODEL FIX STUDY REFUSED: {e}", file=sys.stderr)
        return REFUSED

    md_path, json_path, csv_path = H.write_report(result, out, stamp)
    extra = extras(result.per_game, legacy)
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(extra)
        f.write(
            f"\nIncumbent frame fingerprint: `{fingerprint_hash(fp_legacy)}` "
            f"({fp_legacy['rows']} rows); candidate: `{fingerprint_hash(fp)}` ({fp['rows']} rows).\n"
        )
    v = result.report["verdict"]
    pair = result.report["comparisons"]["pairs"][MF.CANDIDATE_NAME]["abs_err"]
    summary = (
        f"VERDICT ({row.id}): {v['verdict']} -- paired |err| change {pair['mean']:+.3f} "
        f"[{pair['lo']:+.3f}, {pair['hi']:+.3f}], margin +{MF.NON_INFERIORITY_MARGIN:.2f}"
    )
    print(summary)
    append_step_summary(summary)
    print(f"[model-fix] wrote {md_path}, {json_path.name} and {csv_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
