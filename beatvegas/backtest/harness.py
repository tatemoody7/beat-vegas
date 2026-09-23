"""The shared measurement harness every future model gate imports.

It answers ONE shape of question, the same way every time: given the champion's
scorer and zero or more candidate scorers with the SAME contract as
`model.bv_line.bv_line_for_slate` ((train_played, target) -> bv_line per target
row), how do they do on each held-out test season -- walk-forward, one fit per
season per arm, graded at the REAL consensus 1H close inside
`lines.REAL_1H_CLOSE_WINDOW_H` of kickoff, selected by the champion's own rule
(the top `PCT_SHARE` of each season-week slate by gap, `model.score.slate_bar`)
and capped the way the ledger is capped (`postmortem.weekly_cap`)?

What it refuses to do, by construction (the owner's rules, 2026-09-23):

* choose anything. It reports; no threshold, feature or rule is picked here, no
  `model_runs` row is written, no table is touched. The registry criterion is
  quoted verbatim and, when a criterion FUNCTION is declared, applied -- the
  verdict is a sentence, never a change.
* run without a registry row (`registry.require_runnable_row`) whose status is
  `pre-registered` or `exploratory` and whose criterion cell is non-empty.
* read a proxy line. `proxy_line`, `line_flat`, `line_step` and the full-game
  total never enter a grade; a test season with zero real closes raises
  `GateNotEvaluable` and the report says NOT EVALUABLE.
* grade at a close it cannot prove: `Grading.window_h` must equal
  `REAL_1H_CLOSE_WINDOW_H` exactly.

Two things every report states because they are substitutions, not facts:

* the 2023-25 history holds ZERO `hardrockbet` 1H rows (the purchased close set
  does not carry the book), so on those seasons the CONSENSUS close defines the
  slate universe and stands in for Hard Rock's line -- a declared substitution.
  Where a Hard Rock close exists (2026+), the same rows are graded on it beside.
* both `min_games` knobs default to 0, matching the live board
  (`scripts/weekly_update.py --min-games 0` -> `score_slate`), and the graded
  table is split at `MIN_GAMES_FOR_REAL_MONEY` (2) so the money population reads
  on its own.

The candidate CLV clock is the consensus as of the Friday `fri_pm` build window
(`snapshots.decision_lines`); CLV exists only where that line does (2026+), and
the report says `n_with_decision_line / n_picks`.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .. import postmortem as pm
from ..etl.features import apply_min_games, build_feature_frame, training_frame
from ..etl.frame_fingerprint import write_fingerprint
from ..grading import clv_under, trusted_first_half_total, under_result, units_won
from ..lines import REAL_1H_CLOSE_WINDOW_H
from ..model.bv_line import bv_line_for_slate
from ..model.score import (
    BET_GAP_PTS,
    MIN_GAMES_FOR_REAL_MONEY,
    PCT_SHARE,
    WEEKLY_BET_CAP,
    slate_bar,
)
from ..registry import HarnessRefusal, RegistryRow
from .overfit import deflated_sharpe_ratio, pbo, sr_variance_across_configs
from .reporting import append_step_summary, report_paths
from .residual_gate import GateNotEvaluable, _bias, _clean, _mae, overlap, record, season_span
from .stats import holm_adjust, paired_bootstrap_mean

__all__ = [
    "Arm",
    "Candidate",
    "FIXED_CAVEATS",
    "Grading",
    "HarnessRefusal",
    "HarnessResult",
    "HarnessSpec",
    "PROXY_COLS",
    "arm_metrics",
    "attach_closes",
    "cap_within",
    "compare_arms",
    "favourable_clv",
    "incumbent_arm",
    "load_frame",
    "pct_qualifiers",
    "render_markdown",
    "run",
    "split_populations",
    "verdict",
    "walk_forward",
    "write_report",
]

# (train_played, target) -> bv_line per target row, in target.index order. The
# contract of model.bv_line.bv_line_for_slate; a candidate is anything with it.
Candidate = Callable[[pd.DataFrame, pd.DataFrame], np.ndarray]

# Columns a grade must never read. Their presence in a graded frame is a defect.
PROXY_COLS = ("proxy_line", "line_flat", "line_step", "full_game_total")

INCUMBENT_NAME = "incumbent"
KIND = "harness"

FIXED_CAVEATS: Tuple[str, ...] = (
    "One-shot: this run is one look at the seasons it names. Add the look to the "
    "registry row's `comparisons run` cell; do not re-run to a different answer.",
    "Consensus stands in for Hard Rock before 2026 (declared substitution): the "
    "2023-25 history holds zero `hardrockbet` 1H rows, so on those seasons the consensus "
    "close defines the slate universe and is the line every record is graded at. Where a "
    "Hard Rock close exists the same rows are graded on it beside (the `hr` blocks).",
    "The EV / price gate is NOT reproduced: `card.py::is_bet` needs both sides' closing "
    "prices at the book (`market_read`), which the historical close set does not carry. "
    "Records here are at a flat under price; the live card would have refused some of them.",
    "Per-season folds, not the live weekly refit: each test season is scored by ONE model "
    "fitted on every played prior season, where the board refits every Sunday on whatever "
    "CFBD serves that week.",
    "Selection uses the close's gap (the historical frame has no decision-time line); CLV "
    "is measured only where a decision line exists, from that line to the close, and the "
    "report says `n_with_decision_line / n_picks`.",
    "Both `min_games` knobs are stated in the spec block; the graded table is split at "
    f"{MIN_GAMES_FOR_REAL_MONEY} games so the money population is readable.",
    "The feature frame drops played games whose 1H total equals the proxy line "
    "(`etl.features.build_feature_frame`, a training-target rule); those games are absent "
    "from every count here.",
    "2023-25 EXHAUSTED for rule selection -- this run measures, nothing here may pick a "
    "threshold (docs/HYPOTHESES.md, 2026-09-22).",
)


# ---------------------------------------------------------------- dataclasses


@dataclass(frozen=True)
class Arm:
    name: str
    scorer: Candidate
    is_incumbent: bool = False


def incumbent_arm() -> Arm:
    """The champion as production scores it: model.bv_line.bv_line_for_slate."""
    return Arm(INCUMBENT_NAME, bv_line_for_slate, is_incumbent=True)


@dataclass(frozen=True)
class HarnessSpec:
    row_id: str
    arms: Tuple[Arm, ...]
    test_seasons: Tuple[int, ...]
    min_games_train: int = 0
    min_games_score: int = 0
    fbs_only: bool = True
    share: float = PCT_SHARE
    fallback_bar: float = BET_GAP_PTS
    cap: int = WEEKLY_BET_CAP
    under_price: int = -110
    n_boot: int = 2000
    seed: int = 7
    alpha: float = 0.05
    criterion: Optional[Callable[[Dict[str, Any]], Optional[bool]]] = None

    def __post_init__(self) -> None:
        arms = tuple(self.arms)
        object.__setattr__(self, "arms", arms)
        object.__setattr__(self, "test_seasons", tuple(sorted(int(s) for s in self.test_seasons)))
        if not arms:
            raise HarnessRefusal("HarnessSpec needs at least the incumbent arm")
        inc = [a for a in arms if a.is_incumbent]
        if len(inc) != 1:
            raise HarnessRefusal(f"HarnessSpec needs exactly one incumbent arm, got {len(inc)}")
        names = [a.name for a in arms]
        if len(set(names)) != len(names):
            raise HarnessRefusal(f"arm names must be unique: {names}")
        if not self.test_seasons:
            raise HarnessRefusal("HarnessSpec needs at least one test season")
        if not (0 < self.share <= 1):
            raise HarnessRefusal(f"share must be in (0, 1], got {self.share}")
        if self.min_games_train < 0 or self.min_games_score < 0:
            raise HarnessRefusal("min_games knobs must be >= 0")

    @property
    def incumbent(self) -> Arm:
        return next(a for a in self.arms if a.is_incumbent)

    @property
    def candidates(self) -> Tuple[Arm, ...]:
        return tuple(a for a in self.arms if not a.is_incumbent)

    def describe(self) -> Dict[str, Any]:
        return {
            "row_id": self.row_id,
            "arms": [
                {"name": a.name, "is_incumbent": a.is_incumbent, "scorer": _qualname(a.scorer)}
                for a in self.arms
            ],
            "test_seasons": list(self.test_seasons),
            "min_games_train": self.min_games_train,
            "min_games_score": self.min_games_score,
            "money_population_min_games": MIN_GAMES_FOR_REAL_MONEY,
            "fbs_only": self.fbs_only,
            "share": self.share,
            "fallback_bar": self.fallback_bar,
            "cap": self.cap,
            "under_price": self.under_price,
            "n_boot": self.n_boot,
            "seed": self.seed,
            "alpha": self.alpha,
            "criterion_fn": _qualname(self.criterion) if self.criterion else None,
        }


@dataclass(frozen=True)
class Grading:
    """Everything a grade may read, keyed by game id. `closes` is the consensus
    close inside `window_h` (must be REAL_1H_CLOSE_WINDOW_H); `hr_closes` /
    `hr_prices` Hard Rock's own strict-centred close and under price where the
    book has one; `decision_lines` the candidate bet line under `decision_rule`."""

    closes: Dict[int, float]
    window_h: Optional[float] = REAL_1H_CLOSE_WINDOW_H
    hr_closes: Dict[int, float] = field(default_factory=dict)
    hr_prices: Dict[int, int] = field(default_factory=dict)
    decision_lines: Dict[int, float] = field(default_factory=dict)
    decision_rule: Optional[str] = None

    def __post_init__(self) -> None:
        if self.window_h is None or float(self.window_h) != float(REAL_1H_CLOSE_WINDOW_H):
            raise HarnessRefusal(
                f"Grading.window_h must be exactly REAL_1H_CLOSE_WINDOW_H "
                f"({REAL_1H_CLOSE_WINDOW_H:g} h), got {self.window_h!r}; a close outside that "
                "window is not a real close"
            )

    def describe(self) -> Dict[str, Any]:
        return {
            "close_window_h": self.window_h,
            "n_closes": len(self.closes),
            "n_hr_closes": len(self.hr_closes),
            "n_hr_prices": len(self.hr_prices),
            "n_decision_lines": len(self.decision_lines),
            "decision_rule": self.decision_rule,
        }


@dataclass
class HarnessResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


# ---------------------------------------------------------------- frame


def _qualname(fn: Any) -> Optional[str]:
    if fn is None:
        return None
    mod = getattr(fn, "__module__", None) or "?"
    name = getattr(fn, "__qualname__", None) or getattr(fn, "__name__", None) or repr(fn)
    return f"{mod}.{name}"


def load_frame(
    snapshot: Optional[Path], spec: HarnessSpec, fingerprint_path: Path
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """The feature frame the run is judged on, plus its fingerprint (ALWAYS
    written to `fingerprint_path`, so no report exists without one).

    `snapshot`: a pickle from scripts/frame_snapshot.py carrying
    `attrs["build"]` (fbs_only, min_games, ...). It is refused when it has no
    build attrs (the cut cannot be verified), when its `min_games` cut is
    coarser than the spec's finer knob (rows the spec wants are already gone),
    or when its `fbs_only` differs from the spec. With no snapshot the frame is
    built at the finer of the two knobs; each knob is then applied per
    population by split_populations."""
    finest = min(spec.min_games_train, spec.min_games_score)
    if snapshot is not None:
        frame = pd.read_pickle(Path(snapshot))
        build = frame.attrs.get("build") if isinstance(frame.attrs, dict) else None
        if not isinstance(build, dict):
            raise HarnessRefusal(
                f"snapshot {snapshot} carries no attrs['build']; re-dump it with "
                "scripts/frame_snapshot.py so its cut is declared, not inferred"
            )
        cut = build.get("min_games")
        if cut is None or int(cut) > finest:
            raise HarnessRefusal(
                f"snapshot {snapshot} was cut at min_games={cut!r}, coarser than the spec's "
                f"{finest}; rows the spec wants are not in it"
            )
        if build.get("fbs_only") is not None and bool(build["fbs_only"]) != spec.fbs_only:
            raise HarnessRefusal(
                f"snapshot {snapshot} was built with fbs_only={build['fbs_only']}, spec says "
                f"{spec.fbs_only}"
            )
        source: Dict[str, Any] = {"snapshot": str(snapshot), "build": dict(build)}
    else:
        frame = build_feature_frame(min_games=finest, fbs_only=spec.fbs_only)
        frame.attrs["build"] = {"fbs_only": spec.fbs_only, "min_games": finest}
        source = {"snapshot": None, "build": dict(frame.attrs["build"])}
    fp = write_fingerprint(frame, Path(fingerprint_path))
    fp["source"] = source
    fp["path"] = str(fingerprint_path)
    return frame, fp


def _actuals(df: pd.DataFrame) -> pd.Series:
    """The trusted 1H total per row (grading.trusted_first_half_total), NaN when
    the row cannot be graded."""
    src = df["first_half_source"] if "first_half_source" in df else pd.Series(None, index=df.index)
    hp = df["home_points"] if "home_points" in df else pd.Series(np.nan, index=df.index)
    ap = df["away_points"] if "away_points" in df else pd.Series(np.nan, index=df.index)
    out = []
    for fh, h, a, s in zip(df["first_half_total"], hp, ap, src):
        fh_v = None if pd.isna(fh) else float(fh)
        v = trusted_first_half_total(
            fh_v,
            None if pd.isna(h) else float(h),
            None if pd.isna(a) else float(a),
            None if (s is None or (isinstance(s, float) and math.isnan(s))) else s,
        )
        out.append(np.nan if v is None else float(v))
    return pd.Series(out, index=df.index, dtype=float)


def split_populations(
    frame: pd.DataFrame, spec: HarnessSpec
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """(train_pool, score_pool, drops).

    train_pool: played rows at `min_games_train` -- exactly the rows `score_slate`
    hands the champion (`training_frame` of the frame it is given; no trust
    filter there either, so none here). score_pool: played rows of the test
    seasons at `min_games_score` whose 1H total is TRUSTED
    (grading.trusted_first_half_total); a row that cannot be graded is not
    scored. `drops` counts what each cut removed."""
    for c in ("h_games_played", "a_games_played", "season", "first_half_total", "id"):
        if c not in frame.columns:
            raise ValueError(f"frame lacks column {c!r}; is this a build_feature_frame output?")
    n0 = int(len(frame))
    train_cut = apply_min_games(frame, spec.min_games_train)
    train_pool = training_frame(train_cut)
    score_cut = apply_min_games(frame, spec.min_games_score)
    score_cut = score_cut[score_cut["season"].isin(list(spec.test_seasons))]
    score_played = training_frame(score_cut)
    actual = _actuals(score_played)
    score_pool = score_played[actual.notna()].copy()
    score_pool["actual"] = actual[actual.notna()]
    drops = {
        "frame_rows": n0,
        "train": {
            "after_min_games": int(len(train_cut)),
            "played": int(len(train_pool)),
            "min_games": spec.min_games_train,
        },
        "score": {
            "test_seasons_after_min_games": int(len(score_cut)),
            "played": int(len(score_played)),
            "trusted_actual": int(len(score_pool)),
            "untrusted_dropped": int(len(score_played) - len(score_pool)),
            "min_games": spec.min_games_score,
        },
    }
    return train_pool, score_pool, drops


# ---------------------------------------------------------------- walk-forward


def _kick(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["start_date"], errors="coerce")


def _pred_col(arm: Arm) -> str:
    return f"pred_{arm.name}"


def walk_forward(
    train_pool: pd.DataFrame, score_pool: pd.DataFrame, spec: HarnessSpec
) -> pd.DataFrame:
    """One row per scored game with `pred_<arm>` per arm. For each test season
    s: train = train_pool rows with season < s (every played prior season, as
    production trains), target = score_pool rows of s; one fit per arm. A NaN
    or a length mismatch from a scorer is a defect and raises; an empty train
    or target season is a coverage state and raises GateNotEvaluable."""
    rows: List[pd.DataFrame] = []
    for s in spec.test_seasons:
        train = train_pool[train_pool["season"] < s]
        target = score_pool[score_pool["season"] == s]
        if target.empty:
            raise GateNotEvaluable(f"test season {s}: no scoreable played row (trusted 1H total)")
        if train.empty:
            raise GateNotEvaluable(f"test season {s}: no played training row from a prior season")
        k_train, k_test = _kick(train), _kick(target)
        n_missing = int(k_train.isna().sum() + k_test.isna().sum())
        if n_missing:
            raise ValueError(
                f"test season {s}: {n_missing} row(s) have no kickoff; order unprovable"
            )
        if not k_train.max() < k_test.min():
            raise ValueError(
                f"test season {s}: latest training kickoff {k_train.max()} is not before the "
                f"earliest test kickoff {k_test.min()}"
            )
        shared = set(train["id"]) & set(target["id"])
        if shared:
            raise ValueError(f"test season {s}: {len(shared)} game id(s) in both train and test")
        out = pd.DataFrame(
            {
                "game_id": target["id"].astype(int).values,
                "season": int(s),
                "week": target["week"].values,
                "kickoff": k_test.values,
                "home_team": target["home_team"].values if "home_team" in target else None,
                "away_team": target["away_team"].values if "away_team" in target else None,
                "actual": pd.to_numeric(target["actual"], errors="coerce").values,
                "h_games_played": pd.to_numeric(target["h_games_played"], errors="coerce").values,
                "a_games_played": pd.to_numeric(target["a_games_played"], errors="coerce").values,
            },
            index=target.index,
        )
        out["games_played_min"] = out[["h_games_played", "a_games_played"]].min(axis=1)
        out["money_population"] = out["games_played_min"] >= MIN_GAMES_FOR_REAL_MONEY
        out["n_train"] = int(len(train))
        for arm in spec.arms:
            pred = np.asarray(arm.scorer(train, target), dtype=float).reshape(-1)
            if len(pred) != len(target):
                raise ValueError(
                    f"arm {arm.name!r}, season {s}: scorer returned {len(pred)} predictions for "
                    f"{len(target)} target rows"
                )
            if not np.all(np.isfinite(pred)):
                bad = int((~np.isfinite(pred)).sum())
                raise ValueError(f"arm {arm.name!r}, season {s}: {bad} non-finite prediction(s)")
            out[_pred_col(arm)] = np.round(pred, 2)
        rows.append(out)
    per_game = pd.concat(rows, ignore_index=True)
    return per_game


# ---------------------------------------------------------------- closes


def _assert_no_proxy(df: pd.DataFrame) -> None:
    bad = [c for c in PROXY_COLS if c in df.columns]
    if bad:
        raise HarnessRefusal(f"a proxy-derived column reached the grade: {bad}")


def attach_closes(per_game: pd.DataFrame, grading: Grading, spec: HarnessSpec) -> pd.DataFrame:
    """The graded frame: rows of `per_game` that carry a real consensus close,
    with outcome / units at `spec.under_price`, `gap_<arm>` = close - pred and
    `err_<arm>` = actual - pred per arm, the Hard Rock basis where the book
    closed the game (`outcome_hr` / `units_hr` at Hard Rock's own under price,
    -110 when its close has no price), and the candidate `decision_line`.
    `attrs["coverage"]` counts per season. GateNotEvaluable for a test season
    with zero real closes."""
    if grading.window_h is None or float(grading.window_h) != float(REAL_1H_CLOSE_WINDOW_H):
        raise HarnessRefusal("attach_closes: Grading.window_h is not REAL_1H_CLOSE_WINDOW_H")
    _assert_no_proxy(per_game)
    df = per_game.copy()
    df["close"] = df["game_id"].map(grading.closes).astype(float)
    coverage: Dict[int, Dict[str, int]] = {}
    for s in spec.test_seasons:
        sub = df[df["season"] == s]
        n_close = int(sub["close"].notna().sum())
        coverage[int(s)] = {
            "scoreable": int(len(sub)),
            "with_close": n_close,
            "with_hr_close": int(sub["game_id"].isin(list(grading.hr_closes)).sum()),
            "with_decision_line": int(sub["game_id"].isin(list(grading.decision_lines)).sum()),
        }
        if n_close == 0:
            raise GateNotEvaluable(
                f"test season {s}: zero real 1H closes inside {REAL_1H_CLOSE_WINDOW_H:g} h of "
                f"kickoff on {len(sub)} scoreable games; the consensus close defines the universe "
                "and none exists, so the season is NOT EVALUABLE (no proxy line is read)"
            )
    df = df[df["close"].notna()].copy()
    df["market_err"] = df["actual"] - df["close"]
    df["outcome"] = [under_result(a, c) for a, c in zip(df["actual"], df["close"])]
    df["units"] = [units_won(a, c, spec.under_price) for a, c in zip(df["actual"], df["close"])]
    df["hr_close"] = df["game_id"].map(grading.hr_closes).astype(float)
    df["hr_price"] = df["game_id"].map(grading.hr_prices)
    has_hr = df["hr_close"].notna()
    df["outcome_hr"] = None
    df["units_hr"] = np.nan
    if has_hr.any():
        sub = df[has_hr]
        df.loc[has_hr, "outcome_hr"] = [
            under_result(a, c) for a, c in zip(sub["actual"], sub["hr_close"])
        ]
        df.loc[has_hr, "units_hr"] = [
            units_won(a, c, int(p) if not pd.isna(p) else spec.under_price)
            for a, c, p in zip(sub["actual"], sub["hr_close"], sub["hr_price"])
        ]
    df["decision_line"] = df["game_id"].map(grading.decision_lines).astype(float)
    for arm in spec.arms:
        p = df[_pred_col(arm)]
        df[f"gap_{arm.name}"] = (df["close"] - p).round(2)
        df[f"err_{arm.name}"] = df["actual"] - p
        df[f"gap_hr_{arm.name}"] = (df["hr_close"] - p).round(2)
    df = df.reset_index(drop=True)
    df.attrs["coverage"] = coverage
    return df


# ---------------------------------------------------------------- selection


def pct_qualifiers(
    per_game: pd.DataFrame,
    gap_col: str,
    share: float = PCT_SHARE,
    fallback_bar: float = BET_GAP_PTS,
    slate_key: Sequence[str] = ("season", "week"),
) -> Tuple[pd.Series, pd.Series]:
    """(qualifies, bar) per row under the champion's rule: per slate (default a
    season-week) the bar is `slate_bar(gaps, share)` -- the k-th largest gap,
    k = max(1, round(share * N)) -- and a game qualifies when gap >= bar AND
    gap > 0; ties at the bar all qualify, a gap <= 0 never does. A slate with
    no gap at all takes `fallback_bar` (BET_GAP_PTS, the empty-slate fallback
    the card uses)."""
    gaps = pd.to_numeric(per_game[gap_col], errors="coerce")
    bar = pd.Series(np.nan, index=per_game.index, dtype=float)
    keys = list(slate_key)
    for _, idx in per_game.groupby(keys, sort=False, dropna=False).groups.items():
        g = gaps.loc[idx]
        b = slate_bar([v for v in g.tolist() if not pd.isna(v)], share)
        bar.loc[idx] = float(fallback_bar) if b is None else float(b)
    qualifies = gaps.notna() & (gaps >= bar) & (gaps > 0)
    return qualifies.astype(bool), bar


def cap_within(
    per_game: pd.DataFrame, gap_col: str, qualifies: pd.Series, cap: int = WEEKLY_BET_CAP
) -> pd.Series:
    """The weekly cap on the QUALIFYING subset: top `cap` per season-week by
    gap, ties by kickoff then game_id (postmortem.weekly_cap with no minimum
    gap -- qualification already required gap > 0)."""
    q = qualifies.reindex(per_game.index, fill_value=False).astype(bool)
    sub = per_game[q]
    mask = pd.Series(False, index=per_game.index)
    if sub.empty:
        return mask
    keep = pm.weekly_cap(
        sub, gap_col, cap=cap, min_gap=float("-inf"), tie_cols=["kickoff", "game_id"]
    )
    mask.loc[keep[keep].index] = True
    return mask


def favourable_clv(bet_line: Optional[float], closing_line: Optional[float]) -> Optional[float]:
    """Line value in the FAVOURABLE direction for an under: -(clv_under). The one
    sign flip in Python -- grading.clv_under stores closing - bet, where a
    falling line (negative) is the good one; here +1.0 means the market came a
    point toward us. Mirrors web/lib/decision-quality.ts::favourable."""
    c = clv_under(bet_line, closing_line)
    if c is None or (isinstance(c, float) and math.isnan(c)):
        return None
    return -float(c)


def _select(per_game: pd.DataFrame, arm: Arm, spec: HarnessSpec) -> pd.DataFrame:
    """Adds qual_/cap_/bar_ (consensus basis), qual_hr_ (Hard Rock basis, over
    the rows Hard Rock closed) and clv_fav_ per arm."""
    df = per_game
    gap_col = f"gap_{arm.name}"
    q, bar = pct_qualifiers(df, gap_col, spec.share, spec.fallback_bar)
    df[f"qual_{arm.name}"] = q
    df[f"bar_{arm.name}"] = bar
    df[f"cap_{arm.name}"] = cap_within(df, gap_col, q, spec.cap)
    hr_rows = df[df["hr_close"].notna()]
    qh = pd.Series(False, index=df.index)
    if not hr_rows.empty:
        qhr, _ = pct_qualifiers(hr_rows, f"gap_hr_{arm.name}", spec.share, spec.fallback_bar)
        qh.loc[qhr[qhr].index] = True
    df[f"qual_hr_{arm.name}"] = qh
    df[f"clv_fav_{arm.name}"] = [
        favourable_clv(b, c) if (qq and not pd.isna(b)) else np.nan
        for qq, b, c in zip(q, df["decision_line"], df["close"])
    ]
    return df


# ---------------------------------------------------------------- metrics


def _rec(df: pd.DataFrame, mask: pd.Series, basis: str = "") -> Dict[str, Any]:
    suffix = f"_{basis}" if basis else ""
    return record(df, mask, outcome_col=f"outcome{suffix}", units_col=f"units{suffix}")


def _block(df: pd.DataFrame, arm: Arm, spec: HarnessSpec, incumbent: Arm) -> Dict[str, Any]:
    n = int(len(df))
    pred = df[_pred_col(arm)]
    gap = df[f"gap_{arm.name}"]
    q = df[f"qual_{arm.name}"].astype(bool)
    c = df[f"cap_{arm.name}"].astype(bool)
    all_mask = pd.Series(True, index=df.index)
    bias_ap = _bias(df["actual"], pred)
    money = df["money_population"].astype(bool)
    hr_rows = df[df["hr_close"].notna()]
    hr_block: Optional[Dict[str, Any]] = None
    if not hr_rows.empty:
        qh = hr_rows[f"qual_hr_{arm.name}"].astype(bool)
        hr_block = {
            "n": int(len(hr_rows)),
            "n_priced": int(hr_rows["hr_price"].notna().sum()),
            "mae": _mae(hr_rows["actual"], hr_rows[_pred_col(arm)]),
            "hr_mae": _mae(hr_rows["actual"], hr_rows["hr_close"]),
            "share_pct": float(qh.mean()) if len(hr_rows) else None,
            "record_all": _rec(hr_rows, pd.Series(True, index=hr_rows.index), "hr"),
            "record_pct": _rec(hr_rows, qh, "hr"),
        }
    clv = df.loc[q, f"clv_fav_{arm.name}"]
    clv_vals = clv.dropna()
    clv_block = {
        "n_picks": int(q.sum()),
        "n_with_decision_line": int(len(clv_vals)),
        "mean_favourable": float(clv_vals.mean()) if len(clv_vals) else None,
        "bootstrap": paired_bootstrap_mean(
            clv_vals.tolist(), n_boot=spec.n_boot, seed=spec.seed, alpha=spec.alpha
        )
        if len(clv_vals)
        else None,
    }
    block: Dict[str, Any] = {
        "n": n,
        "mae": _mae(df["actual"], pred),
        "market_mae": _mae(df["actual"], df["close"]),
        "bias_actual_minus_pred": bias_ap,
        "bias_pred_minus_actual": None if bias_ap is None else -bias_ap,
        "pred_mean": float(pred.mean()) if n else None,
        "close_mean": float(df["close"].mean()) if n else None,
        "actual_mean": float(df["actual"].mean()) if n else None,
        "share_pct": float(q.mean()) if n else None,
        "share_const": float((gap >= spec.fallback_bar).mean()) if n else None,
        "bar_median": float(df[f"bar_{arm.name}"].median()) if n else None,
        "record_all": _rec(df, all_mask),
        "record_pct": _rec(df, q),
        "record_cap": _rec(df, c),
        "by_games_played": {
            f"ge{MIN_GAMES_FOR_REAL_MONEY}": {
                "n": int(money.sum()),
                "record_pct": _rec(df, q & money),
                "record_cap": _rec(df, c & money),
            },
            f"lt{MIN_GAMES_FOR_REAL_MONEY}": {
                "n": int((~money).sum()),
                "record_pct": _rec(df, q & ~money),
                "record_cap": _rec(df, c & ~money),
            },
        },
        "hr": hr_block,
        "clv": clv_block,
    }
    if not arm.is_incumbent:
        block["overlap_vs_incumbent"] = {
            "pct": overlap(q, df[f"qual_{incumbent.name}"].astype(bool)),
            "cap": overlap(c, df[f"cap_{incumbent.name}"].astype(bool)),
        }
    return block


def arm_metrics(
    per_game: pd.DataFrame, arm: Arm, incumbent: Arm, spec: HarnessSpec
) -> Dict[str, Any]:
    """Per test season and pooled: accuracy (MAE, bias in both signs, labelled),
    the market's own MAE on the same rows, selection shares under the
    percentile rule and the retired constant bar, records for pct / cap / all,
    the split at MIN_GAMES_FOR_REAL_MONEY, the Hard Rock basis where present,
    CLV where a decision line exists, and pick-set overlap with the incumbent."""
    out: Dict[str, Any] = {
        "name": arm.name,
        "is_incumbent": arm.is_incumbent,
        "scorer": _qualname(arm.scorer),
        "seasons": {},
    }
    for s in spec.test_seasons:
        sub = per_game[per_game["season"] == s]
        if sub.empty:
            continue
        out["seasons"][int(s)] = _block(sub, arm, spec, incumbent)
    out["pooled"] = _block(per_game, arm, spec, incumbent)
    return out


def _portfolio(df: pd.DataFrame, arm: Arm) -> pd.Series:
    q = df[f"qual_{arm.name}"].astype(bool)
    return pd.to_numeric(df["units"], errors="coerce").fillna(0.0).where(q, 0.0)


def compare_arms(per_game: pd.DataFrame, spec: HarnessSpec) -> Dict[str, Any]:
    """Each candidate against the incumbent, paired on the game: |err| (negative
    = candidate more accurate), err (a constant difference is flagged
    `deterministic`), and portfolio units per game (units where the arm
    qualifies, else 0). Holm across the candidates per family; deflated Sharpe
    per arm over its qualifying picks with n_trials = number of arms; PBO over
    all arms' per-game portfolio units when there are >= 2 candidates and >= 4
    groups, else None with a note."""
    inc = spec.incumbent
    df = per_game
    pairs: Dict[str, Dict[str, Any]] = {}
    err_inc = df[f"err_{inc.name}"]
    port_inc = _portfolio(df, inc)
    for arm in spec.candidates:
        err_a = df[f"err_{arm.name}"]
        diff = (err_a - err_inc).to_numpy(dtype=float)
        kw = {"n_boot": spec.n_boot, "seed": spec.seed, "alpha": spec.alpha}
        err_bs = paired_bootstrap_mean(err_a.tolist(), err_inc.tolist(), **kw)
        err_bs["deterministic"] = bool(len(diff) and np.nanmax(diff) == np.nanmin(diff))
        pairs[arm.name] = {
            "abs_err": paired_bootstrap_mean(err_a.abs().tolist(), err_inc.abs().tolist(), **kw),
            "err": err_bs,
            "portfolio_units": paired_bootstrap_mean(
                _portfolio(df, arm).tolist(), port_inc.tolist(), **kw
            ),
        }
    holm: Dict[str, Dict[str, Optional[float]]] = {}
    names = [a.name for a in spec.candidates]
    for fam in ("abs_err", "err", "portfolio_units"):
        ps = [pairs[n][fam]["p"] for n in names]
        holm[fam] = dict(zip(names, holm_adjust(ps)))
    # Overfit controls
    pick_returns = {
        a.name: df.loc[df[f"qual_{a.name}"].astype(bool), "units"].astype(float).tolist()
        for a in spec.arms
    }
    sr_var = sr_variance_across_configs(list(pick_returns.values()))
    dsr: Dict[str, Optional[float]] = {}
    for a in spec.arms:
        r = pick_returns[a.name]
        v = deflated_sharpe_ratio(r, len(spec.arms), sr_var) if len(r) > 1 else float("nan")
        dsr[a.name] = None if (isinstance(v, float) and math.isnan(v)) else float(v)
    pbo_val: Optional[float] = None
    if len(spec.candidates) >= 2 and len(df) >= 4:
        matrix = np.column_stack([_portfolio(df, a).to_numpy(dtype=float) for a in spec.arms])
        v = pbo(matrix.tolist())
        pbo_val = None if math.isnan(v) else float(v)
        pbo_note = f"CSCV over {len(spec.arms)} arms x {len(df)} games"
    else:
        pbo_note = (
            "not computed: PBO needs >= 2 candidate arms and >= 4 groups of games "
            f"(have {len(spec.candidates)} candidate(s), {len(df)} games)"
        )
    return {
        "incumbent": inc.name,
        "pairs": pairs,
        "holm": holm,
        "dsr": {"per_arm": dsr, "n_trials": len(spec.arms), "sr_variance": sr_var},
        "pbo": pbo_val,
        "pbo_note": pbo_note,
    }


# ---------------------------------------------------------------- verdict


def verdict(report: Dict[str, Any], spec: HarnessSpec, row: RegistryRow) -> Dict[str, Any]:
    """The verdict SENTENCE. An exploratory row is measurement only: 'n/a', and a
    criterion function is REFUSED (there is nothing to judge). A pre-registered
    row without a function is 'not evaluable' with the registered text quoted;
    with one, the function reads the report and answers True / False / None ->
    met / not met / not evaluable, and its module.qualname is printed beside the
    verbatim criterion so the reader can check the code against the words."""
    text = row.criterion
    if row.status == "exploratory":
        if spec.criterion is not None:
            raise HarnessRefusal(
                f"row {row.id} is exploratory (measurement only); a criterion function "
                f"({_qualname(spec.criterion)}) is refused"
            )
        return {
            "status": row.status,
            "verdict": "n/a (exploratory: measurement only)",
            "criterion_text": text,
            "criterion_fn": None,
        }
    if spec.criterion is None:
        return {
            "status": row.status,
            "verdict": "not evaluable (no criterion function declared; the registered text is below)",
            "criterion_text": text,
            "criterion_fn": None,
        }
    answer = spec.criterion(report)
    word = "met" if answer is True else ("not met" if answer is False else "not evaluable")
    return {
        "status": row.status,
        "verdict": word,
        "criterion_text": text,
        "criterion_fn": _qualname(spec.criterion),
        "criterion_answer": None if answer is None else bool(answer),
    }


# ---------------------------------------------------------------- run


def _fingerprint_summary(fp: Dict[str, Any]) -> Dict[str, Any]:
    keep = (
        "rows",
        "by_season",
        "platform",
        "python",
        "sklearn",
        "numpy",
        "pandas",
        "generated_at",
        "path",
        "source",
    )
    return {k: fp.get(k) for k in keep if k in fp}


def _market(df: pd.DataFrame, spec: HarnessSpec) -> Dict[str, Any]:
    out: Dict[str, Any] = {"seasons": {}}
    for s in spec.test_seasons:
        sub = df[df["season"] == s]
        if sub.empty:
            continue
        out["seasons"][int(s)] = {
            "n": int(len(sub)),
            "close_mae": _mae(sub["actual"], sub["close"]),
            "close_bias_actual_minus_close": _bias(sub["actual"], sub["close"]),
            "blanket_under": _rec(sub, pd.Series(True, index=sub.index)),
        }
    out["pooled"] = {
        "n": int(len(df)),
        "close_mae": _mae(df["actual"], df["close"]),
        "close_bias_actual_minus_close": _bias(df["actual"], df["close"]),
        "blanket_under": _rec(df, pd.Series(True, index=df.index)),
    }
    return out


def run(
    frame: pd.DataFrame,
    grading: Grading,
    spec: HarnessSpec,
    registry_row: RegistryRow,
    fingerprint: Dict[str, Any],
) -> HarnessResult:
    """Measure. Refuses a row the harness may not run (registry rules), raises
    GateNotEvaluable when a test season has no real close, and otherwise
    returns the per-game frame and the report dict (JSON-clean)."""
    if registry_row.id != spec.row_id:
        raise HarnessRefusal(
            f"spec names row {spec.row_id!r} but the registry row is {registry_row.id!r}"
        )
    if not registry_row.runnable:
        raise HarnessRefusal(
            f"row {registry_row.id} is not runnable (status {registry_row.status!r}, "
            f"criterion {'present' if registry_row.criterion.strip() else 'EMPTY'})"
        )
    train_pool, score_pool, drops = split_populations(frame, spec)
    per_game = walk_forward(train_pool, score_pool, spec)
    graded = attach_closes(per_game, grading, spec)
    for arm in spec.arms:
        graded = _select(graded, arm, spec)
    inc = spec.incumbent
    arms = {a.name: arm_metrics(graded, a, inc, spec) for a in spec.arms}
    comparisons = compare_arms(graded, spec)
    seasons_2325 = [s for s in spec.test_seasons if s < 2026]
    report: Dict[str, Any] = {
        "kind": KIND,
        "registry": asdict(registry_row),
        "frame": _fingerprint_summary(fingerprint),
        "spec": spec.describe(),
        "grading": grading.describe(),
        "data_basis": {
            "drops": drops,
            "coverage": graded.attrs.get("coverage", {}),
            "train_seasons_by_test_season": {
                int(s): season_span(train_pool.loc[train_pool["season"] < s, "season"].unique())
                for s in spec.test_seasons
            },
            "substitution": (
                "consensus close stands in for Hard Rock's line on "
                f"{season_span(seasons_2325) if seasons_2325 else 'no'} test season(s) "
                "(zero `hardrockbet` 1H rows in the 2023-25 history); Hard Rock basis reported "
                "beside it where the book closed the game"
            ),
            "close_rule": f"consensus close inside {REAL_1H_CLOSE_WINDOW_H:g} h of kickoff (lines.real_closes)",
            "decision_rule": grading.decision_rule,
        },
        "market": _market(graded, spec),
        "arms": arms,
        "comparisons": comparisons,
        "overfit": {
            "dsr": comparisons["dsr"],
            "pbo": comparisons["pbo"],
            "pbo_note": comparisons["pbo_note"],
        },
        "caveats": list(FIXED_CAVEATS),
    }
    report["verdict"] = verdict(report, spec, registry_row)
    return HarnessResult(per_game=graded, report=_clean(report))


# ---------------------------------------------------------------- rendering


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _num(v: Optional[float], fmt: str = "{:+.2f}") -> str:
    return "—" if v is None else fmt.format(v)


def _wlp(r: Dict[str, Any]) -> str:
    return f"{r['wins']}-{r['losses']}-{r['pushes']}P"


def _ci(r: Dict[str, Any]) -> str:
    if r.get("ci_lo") is None:
        return "—"
    return f"{100 * r['ci_lo']:.1f}–{100 * r['ci_hi']:.1f}%"


def _roi(r: Dict[str, Any]) -> str:
    return _pct(r.get("roi")) if r.get("roi") is not None else "—"


def _rec_row(label: str, r: Dict[str, Any]) -> str:
    return (
        f"| {label} | {r['n']} | {_wlp(r)} | {_pct(r.get('hit_rate'))} | {_ci(r)} | "
        f"{r['units']:+.2f} | {_roi(r)} |"
    )


def _bs(b: Optional[Dict[str, Any]]) -> str:
    if not b or b.get("mean") is None:
        return "—"
    det = " (deterministic)" if b.get("deterministic") else ""
    return f"{b['mean']:+.3f} [{b['lo']:+.3f}, {b['hi']:+.3f}] p={b['p']:.3f}{det}"


def render_markdown(report: Dict[str, Any]) -> str:
    rep = report
    reg = rep["registry"]
    spec = rep["spec"]
    fr = rep["frame"]
    v = rep["verdict"]
    L: List[str] = [
        f"# Measurement harness — {reg['id']} ({reg['status']})",
        "",
        f"**Question.** {reg['question']}",
        "",
        "## Verdict",
        "",
        f"**{v['verdict']}**"
        + (f" — criterion function `{v['criterion_fn']}`" if v.get("criterion_fn") else ""),
        "",
        "Registered criterion, verbatim:",
        "",
        f"> {v['criterion_text']}",
        "",
        "## Frame",
        "",
        f"- rows {fr.get('rows')} · by season {fr.get('by_season')} · sklearn {fr.get('sklearn')} · "
        f"python {fr.get('python')} · {fr.get('platform')}",
        f"- fingerprint `{fr.get('path')}` · source {fr.get('source')}",
        "",
        "## Spec",
        "",
        f"- row `{spec['row_id']}` · test seasons {spec['test_seasons']} · arms "
        + ", ".join(
            f"`{a['name']}`{' (incumbent)' if a['is_incumbent'] else ''}" for a in spec["arms"]
        ),
        f"- min_games_train = {spec['min_games_train']}, min_games_score = {spec['min_games_score']} "
        f"(live board: 0 / 0); money population = min games played >= "
        f"{spec['money_population_min_games']}",
        f"- rule: top {100 * spec['share']:.0f}% of each season-week slate by gap (`slate_bar`), "
        f"fallback bar {spec['fallback_bar']} on an empty slate, cap {spec['cap']} per week, "
        f"under at {spec['under_price']}; bootstrap n={spec['n_boot']} seed={spec['seed']} "
        f"alpha={spec['alpha']}",
        f"- fbs_only = {spec['fbs_only']}",
        "",
        "## Data basis",
        "",
        f"- {rep['data_basis']['close_rule']}",
        f"- {rep['data_basis']['substitution']}",
        f"- decision rule (candidate bet line for CLV): `{rep['data_basis']['decision_rule']}`",
        "",
        "| Test season | trained on | scoreable | with real close | with Hard Rock close | with decision line |",
        "|---|---|---|---|---|---|",
    ]
    cov = rep["data_basis"]["coverage"]
    trained = rep["data_basis"]["train_seasons_by_test_season"]
    for s, c in cov.items():
        L.append(
            f"| {s} | {trained.get(str(s), trained.get(s, '—'))} | {c['scoreable']} | "
            f"{c['with_close']} | {c['with_hr_close']} | {c['with_decision_line']} |"
        )
    d = rep["data_basis"]["drops"]
    L += [
        "",
        f"Frame rows {d['frame_rows']}; training pool {d['train']['played']} played rows at "
        f"min_games {d['train']['min_games']}; score pool {d['score']['trusted_actual']} trusted "
        f"rows at min_games {d['score']['min_games']} ({d['score']['untrusted_dropped']} played "
        "rows dropped for an untrusted 1H total).",
        "",
        "## Market benchmark (consensus close vs actual)",
        "",
        "| Season | n | Close MAE | Bias (actual − close) | Blanket under W-L-P | Hit % | Units |",
        "|---|---|---|---|---|---|---|",
    ]
    mk = rep["market"]
    for s, m in list(mk["seasons"].items()) + [("pooled", mk["pooled"])]:
        bu = m["blanket_under"]
        L.append(
            f"| {s} | {m['n']} | {_num(m['close_mae'], '{:.2f}')} | "
            f"{_num(m['close_bias_actual_minus_close'])} | {_wlp(bu)} | "
            f"{_pct(bu.get('hit_rate'))} | {bu['units']:+.2f} |"
        )
    L += ["", "## Arms", ""]
    for name, a in rep["arms"].items():
        L += [
            f"### `{name}`" + (" (incumbent)" if a["is_incumbent"] else "") + f" — `{a['scorer']}`",
            "",
            "| Season | n | MAE | market MAE | Bias (actual − pred) | Bias (pred − actual) | "
            "share pct | share ≥ const | bar (median) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        blocks = list(a["seasons"].items()) + [("pooled", a["pooled"])]
        for s, b in blocks:
            L.append(
                f"| {s} | {b['n']} | {_num(b['mae'], '{:.2f}')} | {_num(b['market_mae'], '{:.2f}')} | "
                f"{_num(b['bias_actual_minus_pred'])} | {_num(b['bias_pred_minus_actual'])} | "
                f"{_pct(b['share_pct'])} | {_pct(b['share_const'])} | {_num(b['bar_median'], '{:.2f}')} |"
            )
        L += [
            "",
            "| Season | selection | n | W-L-P | Hit % | 95% CI | Units | ROI |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for s, b in blocks:
            for sel in ("all", "pct", "cap"):
                L.append(_rec_row(f"{s} | {sel}", b[f"record_{sel}"]))
        L += [
            "",
            f"Money population (min games played ≥ {spec['money_population_min_games']}) vs the rest, "
            "pct selection:",
            "",
            "| Season | population | n games | W-L-P | Hit % | 95% CI | Units | ROI |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for s, b in blocks:
            for k, grp in b["by_games_played"].items():
                r = grp["record_pct"]
                L.append(
                    f"| {s} | {k} | {grp['n']} | {_wlp(r)} | {_pct(r.get('hit_rate'))} | {_ci(r)} | "
                    f"{r['units']:+.2f} | {_roi(r)} |"
                )
        hr_rows = [(s, b["hr"]) for s, b in blocks if b.get("hr")]
        if hr_rows:
            L += [
                "",
                "Hard Rock basis (rows the book closed; its own strict-centred close, its own under "
                "price where priced, else the flat price):",
                "",
                "| Season | n | n priced | MAE | HR MAE | share pct | all W-L-P | pct W-L-P | pct Units |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            for s, h in hr_rows:
                L.append(
                    f"| {s} | {h['n']} | {h['n_priced']} | {_num(h['mae'], '{:.2f}')} | "
                    f"{_num(h['hr_mae'], '{:.2f}')} | {_pct(h['share_pct'])} | "
                    f"{_wlp(h['record_all'])} | {_wlp(h['record_pct'])} | "
                    f"{h['record_pct']['units']:+.2f} |"
                )
        L += [
            "",
            "Line value (favourable = market came toward us; bet line = the decision rule's "
            "consensus, close = consensus close):",
            "",
            "| Season | picks | with decision line | mean favourable CLV | bootstrap |",
            "|---|---|---|---|---|",
        ]
        for s, b in blocks:
            cl = b["clv"]
            L.append(
                f"| {s} | {cl['n_picks']} | {cl['n_with_decision_line']} | "
                f"{_num(cl['mean_favourable'])} | {_bs(cl['bootstrap'])} |"
            )
        if a.get("pooled", {}).get("overlap_vs_incumbent"):
            o = a["pooled"]["overlap_vs_incumbent"]
            L += [
                "",
                f"Overlap with the incumbent's picks (pooled): pct both {o['pct']['both']} / only "
                f"this {o['pct']['only_a']} / only incumbent {o['pct']['only_b']} (Jaccard "
                f"{_num(o['pct']['jaccard'], '{:.2f}')}); cap both {o['cap']['both']} / only this "
                f"{o['cap']['only_a']} / only incumbent {o['cap']['only_b']}.",
            ]
        L.append("")
    cmp_ = rep["comparisons"]
    if cmp_["pairs"]:
        L += [
            "## Comparisons (candidate − incumbent, paired on the game)",
            "",
            "| Candidate | Δ \\|err\\| (− = more accurate) | Δ err | Δ portfolio units / game | "
            "Holm p (\\|err\\| / err / units) |",
            "|---|---|---|---|---|",
        ]
        for name, p in cmp_["pairs"].items():
            hp = cmp_["holm"]
            L.append(
                f"| `{name}` | {_bs(p['abs_err'])} | {_bs(p['err'])} | {_bs(p['portfolio_units'])} | "
                f"{_num(hp['abs_err'].get(name), '{:.3f}')} / {_num(hp['err'].get(name), '{:.3f}')} / "
                f"{_num(hp['portfolio_units'].get(name), '{:.3f}')} |"
            )
        L.append("")
    ov = rep["overfit"]
    L += [
        "## Overfit controls",
        "",
        f"- Deflated Sharpe per arm (n_trials {ov['dsr']['n_trials']}, SR variance "
        f"{_num(ov['dsr']['sr_variance'], '{:.4f}')}): "
        + ", ".join(f"`{k}` {_num(v, '{:.3f}')}" for k, v in ov["dsr"]["per_arm"].items()),
        (
            f"- PBO: {_num(ov['pbo'], '{:.3f}')} — {ov['pbo_note']}"
            if ov["pbo"] is not None
            else f"- PBO: {ov['pbo_note']}"
        ),
        "",
        "## Caveats",
        "",
    ]
    L += [f"- {c}" for c in rep["caveats"]]
    L.append("")
    return "\n".join(L)


def write_report(
    result: HarnessResult, out: str, stamp: Optional[str] = None
) -> Tuple[Path, Path, Path]:
    """Write <out>_<stamp>.md / .json / .csv and append the markdown to the
    step summary. Returns the three paths."""
    md_path, json_path, csv_path = report_paths(out, stamp)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md = render_markdown(result.report)
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(result.report, indent=2), encoding="utf-8")
    result.per_game.to_csv(csv_path, index=False)
    append_step_summary(md)
    return md_path, json_path, csv_path
