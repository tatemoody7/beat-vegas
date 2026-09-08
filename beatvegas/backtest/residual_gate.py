"""Walk-forward gate for the market-residual 1H engine (PR-3).

One question, answered once: on the held-out test season, does the residual
engine (model/residual.py) select 1H unders better than the incumbent
market-blind BV line (model/bv_line.py) — and does either of them beat the
market itself? The output is the report the owner reads before flipping
config `model.engine`; nothing here changes production behaviour.

The evaluation universe is the test season's played games that carry a REAL
first-half close inside lines.REAL_1H_CLOSE_WINDOW_H of kickoff and a trusted
1H actual (grading.trusted_first_half_total). Both engines are graded at that
same close, as an under at -110, and ranked by the same weekly cap rule
(top 5 per week among gap >= 1.75, ties by kickoff then game id).

Asymmetry, stated up front so the report can say it: the residual engine
trains ONLY on the training seasons' real-close rows (it needs the close as a
feature); the incumbent is refit the way production refits it — on every
played prior-season row — because that is the number it actually puts on the
board. `bv_train_seasons="match"` restricts it to the same seasons instead.

The market benchmark is the close's own MAE against the actual. An engine that
does not beat it adds nothing over reading the line.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import postmortem as pm
from ..grading import under_result, units_won
from ..lines import REAL_1H_CLOSE_WINDOW_H
from ..model import residual as R
from ..model.bv_line import BV_FEATURE_COLS, bv_line_for_slate
from ..model.bv_line import TARGET as BV_TARGET
from ..model.score import MODEL_VERSION as STORED_MODEL_VERSION

__all__ = [
    "GateResult",
    "walk_forward_split",
    "evaluate",
    "cap_picks",
    "record",
    "overlap",
    "render_markdown",
    "under_result",
]

UNDER_PRICE = -110
CAP_TIE_COLS = ("kickoff", "game_id")  # card.apply_weekly_cap's rank minus ev
ENGINES = ("residual", "incumbent", "stored")
SELECTIONS = ("all", "gap175", "cap5")
_SUFFIX = {"residual": "resid", "incumbent": "bv", "stored": "stored"}


@dataclass
class GateResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


# ---------------------------------------------------------------- split


def _kick(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["start_date"], errors="coerce")


def walk_forward_split(df: pd.DataFrame, train_seasons: Sequence[int], test_season: int):
    """(train, test) by season. Raises ValueError unless the game ids are
    disjoint, every test row is the test season, and the latest training
    kickoff precedes the earliest test kickoff."""
    seasons = [int(s) for s in train_seasons]
    train = df[df["season"].isin(seasons)].copy()
    test = df[df["season"] == int(test_season)].copy()
    if test.empty:
        raise ValueError(f"walk_forward_split: no rows for test season {test_season}")
    if train.empty:
        raise ValueError(f"walk_forward_split: no rows for training seasons {seasons}")
    shared = set(train["id"]) & set(test["id"])
    if shared:
        raise ValueError(f"walk_forward_split: {len(shared)} game id(s) in both train and test")
    if not (test["season"] == int(test_season)).all():
        raise ValueError("walk_forward_split: a test row is not the test season")
    last_train, first_test = _kick(train).max(), _kick(test).min()
    if pd.isna(last_train) or pd.isna(first_test):
        raise ValueError("walk_forward_split: a kickoff is missing; cannot prove the order")
    if not last_train < first_test:
        raise ValueError(
            f"walk_forward_split: latest training kickoff {last_train} is not before the "
            f"earliest test kickoff {first_test}"
        )
    return train, test


# ---------------------------------------------------------------- arithmetic


def record(per_game: pd.DataFrame, mask: pd.Series) -> Dict[str, Any]:
    """n / wins / losses / pushes / hit rate / units / ROI / Wilson 95% for the
    under at the close over `mask`. Pushes are staked but excluded from the
    rate, as postmortem.tally does."""
    sub = per_game[mask.reindex(per_game.index, fill_value=False).astype(bool)]
    o = sub["outcome"]
    n = int(len(sub))
    wins, losses, pushes = (
        int((o == "under").sum()),
        int((o == "over").sum()),
        int((o == "push").sum()),
    )
    decided = wins + losses
    units = float(pd.to_numeric(sub["units"], errors="coerce").fillna(0.0).sum()) if n else 0.0
    lo, hi = pm.wilson_ci(wins, decided)
    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": (wins / decided) if decided else None,
        "units": units,
        "roi": (units / n) if n else None,
        "ci_lo": lo,
        "ci_hi": hi,
    }


def cap_picks(per_game: pd.DataFrame, gap_col: str) -> pd.Series:
    """The weekly cap rule (top WEEKLY_CAP per season-week among gap >=
    BET_GAP_PTS), ties by kickoff then game id — the same ranking for every
    engine, independent of the classifier."""
    return pm.weekly_cap(per_game, gap_col, tie_cols=list(CAP_TIE_COLS))


def overlap(a: pd.Series, b: pd.Series) -> Dict[str, Any]:
    """How two pick sets relate: both / only_a / only_b / Jaccard."""
    a = a.astype(bool)
    b = b.reindex(a.index, fill_value=False).astype(bool)
    both, only_a, only_b = int((a & b).sum()), int((a & ~b).sum()), int((~a & b).sum())
    union = both + only_a + only_b
    return {
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "n_a": int(a.sum()),
        "n_b": int(b.sum()),
        "jaccard": (both / union) if union else None,
    }


def _mae(actual: pd.Series, pred: pd.Series) -> Optional[float]:
    d = (pd.to_numeric(actual, errors="coerce") - pd.to_numeric(pred, errors="coerce")).dropna()
    return float(d.abs().mean()) if len(d) else None


def _bias(actual: pd.Series, pred: pd.Series) -> Optional[float]:
    d = (pd.to_numeric(actual, errors="coerce") - pd.to_numeric(pred, errors="coerce")).dropna()
    return float(d.mean()) if len(d) else None


def _calibration(per_game: pd.DataFrame, gap_col: str, pred_col: str) -> List[Dict[str, Any]]:
    """Mean of actual − prediction (and the under rate) within GAP_BANDS."""
    out: List[Dict[str, Any]] = []
    gap = pd.to_numeric(per_game[gap_col], errors="coerce")
    band = gap.map(lambda v: pm.band_label(v, pm.GAP_BANDS))
    for label in [b[2] for b in pm.GAP_BANDS]:
        sub = per_game[band == label]
        if sub.empty:
            continue
        o = sub["outcome"]
        decided = int((o != "push").sum())
        out.append(
            {
                "band": label,
                "n": int(len(sub)),
                "mean_resid": _bias(sub["actual"], sub[pred_col]),
                "hit_rate": (int((o == "under").sum()) / decided) if decided else None,
            }
        )
    return out


def _clean(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    return v


# ---------------------------------------------------------------- evaluate


def _incumbent_frame(
    df_played: pd.DataFrame, train: pd.DataFrame, test_season: int, how: str
) -> pd.DataFrame:
    if how == "match":
        return train
    if how == "all":
        return df_played[df_played["season"] < int(test_season)].copy()
    raise ValueError(f"bv_train_seasons must be 'all' or 'match', got {how!r}")


def _incumbent_fingerprint(bv_train: pd.DataFrame) -> Dict[str, Any]:
    fp = R.fingerprint(bv_train, BV_FEATURE_COLS)
    fp["model_version"] = STORED_MODEL_VERSION
    fp.pop("target_mean", None)
    fp.pop("target_std", None)
    fp["feature_hash"] = hashlib.sha256("|".join(BV_FEATURE_COLS).encode()).hexdigest()[:16]
    return fp


def evaluate(
    df_played: pd.DataFrame,
    closes: Dict[int, float],
    train_seasons: Sequence[int],
    test_season: int,
    stored_bv: Optional[Dict[int, float]] = None,
    bv_train_seasons: str = "all",
) -> GateResult:
    """Run the gate. `df_played`: the played feature frame (features.training_frame)
    for every season involved; `closes`: game_id -> real pre-kick 1H close
    (lines.real_closes, REAL_1H_CLOSE_WINDOW_H); `stored_bv`: game_id -> the
    incumbent's bv_line already in the database, ties the report back to the
    published post-mortem headline."""
    seasons = [int(s) for s in train_seasons]
    test_season = int(test_season)
    train, test = walk_forward_split(df_played, seasons, test_season)
    n_test_played = int(len(test))
    n_test_with_close = int(test["id"].isin(list(closes)).sum())

    # --- residual engine: real-close rows only, both sides
    train_r = R.residual_training_frame(train, closes)
    test_r = R.residual_training_frame(test, closes)
    if test_r.empty:
        raise ValueError(f"no test-season game carries a real 1H close (season {test_season})")
    model = R.fit_residual(train_r)  # raises ResidualFitError under the floor
    r_hat_train = R.predict_residual(model, train_r)
    r_hat_test = R.predict_residual(model, test_r)

    # --- incumbent: refit as production does (every played prior season) and
    # predicted on the same test rows; one fit gives both in-sample and test
    bv_train = _incumbent_frame(df_played, train, test_season, bv_train_seasons)
    _last_bv, _first_test = _kick(bv_train).max(), _kick(test_r).min()
    if not _last_bv < _first_test:
        raise ValueError("incumbent training kickoffs overlap the test season")
    both = pd.concat([bv_train, test_r], ignore_index=True, sort=False)
    bv_pred = bv_line_for_slate(bv_train, both)
    bv_pred_train = np.asarray(bv_pred[: len(bv_train)], dtype=float)
    bv_pred_test = np.asarray(bv_pred[len(bv_train) :], dtype=float)

    # --- per-game frame
    close = test_r[R.LINE_COL].astype(float)
    actual = (test_r[R.TARGET].astype(float) + close).astype(float)
    pg = pd.DataFrame(
        {
            "game_id": test_r["id"].astype(int),
            "season": test_r["season"].astype(int),
            "week": test_r["week"],
            "kickoff": _kick(test_r),
            "home_team": test_r.get("home_team"),
            "away_team": test_r.get("away_team"),
            "close": close,
            "actual": actual,
        }
    )
    pg["outcome"] = [under_result(a, c) for a, c in zip(pg["actual"], pg["close"])]
    pg["units"] = [units_won(a, c, UNDER_PRICE) for a, c in zip(pg["actual"], pg["close"])]
    pg["pred_resid"] = close.to_numpy() + r_hat_test
    pg["gap_resid"] = -r_hat_test
    pg["pred_bv"] = bv_pred_test
    pg["gap_bv"] = pg["close"] - pg["pred_bv"]
    engines = ["residual", "incumbent"]
    if stored_bv is not None:
        pg["pred_stored"] = pg["game_id"].map(stored_bv).astype(float)
        pg["gap_stored"] = pg["close"] - pg["pred_stored"]
        engines.append("stored")
    masks: Dict[str, Dict[str, pd.Series]] = {}
    for eng in engines:
        sfx = _SUFFIX[eng]
        gap = pd.to_numeric(pg[f"gap_{sfx}"], errors="coerce")
        m = {
            "all": pd.Series(True, index=pg.index),
            "gap175": gap.notna() & (gap >= pm.BET_GAP_PTS),
            "cap5": cap_picks(pg, f"gap_{sfx}"),
        }
        pg[f"gap175_{sfx}"] = m["gap175"]
        pg[f"cap5_{sfx}"] = m["cap5"]
        masks[eng] = m

    # --- report
    close_mae = _mae(pg["actual"], pg["close"])
    eng_reports: Dict[str, Any] = {}
    for eng in engines:
        sfx = _SUFFIX[eng]
        pred_col = f"pred_{sfx}"
        rep: Dict[str, Any] = {
            "selections": {sel: record(pg, masks[eng][sel]) for sel in SELECTIONS},
            "n_pred": int(pg[pred_col].notna().sum()),
            "mae": _mae(pg["actual"], pg[pred_col]),
            "bias_test": _bias(pg["actual"], pg[pred_col]),
            "calibration": _calibration(pg, f"gap_{sfx}", pred_col),
        }
        rep["mae_minus_close"] = (
            (rep["mae"] - close_mae) if (rep["mae"] is not None and close_mae is not None) else None
        )
        if eng == "residual":
            rep.update(
                {
                    "train_seasons": sorted(int(s) for s in train_r["season"].unique()),
                    "n_train": int(len(train_r)),
                    "train_rows_are": "training-season games with a real 1H close",
                    "bias_train": _bias(
                        train_r[R.TARGET].astype(float), pd.Series(r_hat_train, index=train_r.index)
                    ),
                }
            )
        elif eng == "incumbent":
            rep.update(
                {
                    "train_seasons": sorted(int(s) for s in bv_train["season"].unique()),
                    "n_train": int(len(bv_train)),
                    "train_rows_are": (
                        "every played prior season"
                        if bv_train_seasons == "all"
                        else "the residual's training seasons only"
                    ),
                    "bias_train": _bias(
                        bv_train[BV_TARGET].astype(float),
                        pd.Series(bv_pred_train, index=bv_train.index),
                    ),
                }
            )
        else:
            rep.update(
                {
                    "train_seasons": None,
                    "n_train": None,
                    "train_rows_are": f"stored predictions tagged {STORED_MODEL_VERSION}",
                    "bias_train": None,
                }
            )
        eng_reports[eng] = rep

    ov = {
        sel: dict(
            a="residual", b="incumbent", **overlap(masks["residual"][sel], masks["incumbent"][sel])
        )
        for sel in ("cap5", "gap175")
    }
    if "stored" in masks:
        ov_stored = {
            sel: dict(
                a="residual", b="stored", **overlap(masks["residual"][sel], masks["stored"][sel])
            )
            for sel in ("cap5", "gap175")
        }
    else:
        ov_stored = None

    fp = R.fingerprint(train_r, R.RESIDUAL_FEATURE_COLS)
    fp["missing_features"] = sorted(
        set(R.missing_required(train_r)) | set(R.missing_required(test_r))
    )
    n_all = eng_reports["residual"]["selections"]["all"]["n"]
    breakeven = 100.0 / 210.0  # -110 both sides
    ci_bits = []
    for e in engines:
        r = eng_reports[e]["selections"]["cap5"]
        if r["ci_lo"] is None:
            ci_bits.append(f"{e} cap-5: no decided games")
            continue
        verdict = (
            "straddles breakeven"
            if r["ci_lo"] <= breakeven <= r["ci_hi"]
            else ("clears breakeven" if r["ci_lo"] > breakeven else "sits below breakeven")
        )
        ci_bits.append(
            f"{e} cap-5 n={r['n']}, 95% CI {100 * r['ci_lo']:.1f}–{100 * r['ci_hi']:.1f}% "
            f"({verdict})"
        )
    caveats = [
        "This is a one-shot test of the residual engine on the held-out season — do not tune "
        f"anything against the {test_season} result. A second look at the same season is no "
        "longer out-of-sample.",
        f"Sample: {n_all} test-season games carry a real 1H close inside "
        f"{REAL_1H_CLOSE_WINDOW_H:g} h of kickoff and a trusted 1H actual, out of {n_test_played} "
        f"played ({n_test_with_close} had any real close). The cap-5 sets are much smaller "
        f"and their Wilson intervals correspondingly wide — {'; '.join(ci_bits)}; breakeven at "
        f"-110 is {100 * breakeven:.1f}%. Read the intervals, not the point estimates.",
        f"Asymmetric training: the incumbent trains on {eng_reports['incumbent']['train_rows_are']}"
        f"{' (how production refits it)' if bv_train_seasons == 'all' else ''} "
        f"({eng_reports['incumbent']['n_train']} rows, seasons "
        f"{eng_reports['incumbent']['train_seasons'][0]}-{eng_reports['incumbent']['train_seasons'][-1]}), "
        f"the residual only on the {'-'.join(str(s)[-2:] if i else str(s) for i, s in enumerate(seasons))} "
        f"real-close rows ({eng_reports['residual']['n_train']} rows). The residual has less data "
        "and a smaller target; the incumbent has more data but never sees the line.",
        "The 'real' closes are the us-region consensus close (The Odds API history, captured "
        "once about 30 minutes before kickoff), not Hard Rock: Hard Rock did not exist historically. "
        "A Hard Rock number can sit off this consensus, and that difference is the live edge the "
        "card reads — none of it is measured here.",
        "Both engines are graded as an under at -110 at that consensus close. No price, "
        "off-market or QB gate could be applied; 'cap5' is the gap gate plus the weekly cap of 5, "
        "ties by kickoff then game id.",
        "The market benchmark is the close's own MAE against the actual. An engine whose MAE is "
        "not below it adds nothing over reading the line; a lower MAE is necessary, not sufficient, "
        "for a betting edge.",
    ]
    if fp["missing_features"]:
        caveats.append(
            f"Residual features absent or all-NaN in the frame: {fp['missing_features']} — the "
            "model conditioned on a NaN column."
        )
    report: Dict[str, Any] = {
        "kind": "residual_gate",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "test_season": test_season,
        "train_seasons": seasons,
        "bv_train_seasons": bv_train_seasons,
        "close_window_h": REAL_1H_CLOSE_WINDOW_H,
        "under_price": UNDER_PRICE,
        "cap": pm.WEEKLY_CAP,
        "min_gap": pm.BET_GAP_PTS,
        "n_test": n_all,
        "n_test_played": n_test_played,
        "n_test_with_close": n_test_with_close,
        "n_test_dropped_untrusted_or_range": n_test_with_close - n_all,
        "close_mae": close_mae,
        "market": {"all": eng_reports["residual"]["selections"]["all"]},
        "engines": eng_reports,
        "overlap": ov,
        "overlap_vs_stored": ov_stored,
        "fingerprint": fp,
        "incumbent_fingerprint": _incumbent_fingerprint(bv_train),
        "caveats": caveats,
    }
    return GateResult(per_game=pg, report=_clean(report))


# ---------------------------------------------------------------- markdown


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _num(v: Optional[float], fmt: str = "{:+.2f}") -> str:
    return "—" if v is None else fmt.format(v)


def _ci(r: Dict[str, Any]) -> str:
    return "—" if r.get("ci_lo") is None else f"{100 * r['ci_lo']:.1f}–{100 * r['ci_hi']:.1f}%"


def _wlp(r: Dict[str, Any]) -> str:
    return f"{r['wins']}-{r['losses']}" + (f"-{r['pushes']}P" if r.get("pushes") else "")


def _roi(r: Dict[str, Any]) -> str:
    return "—" if r.get("roi") is None else f"{100 * r['roi']:+.1f}%"


def _rec_row(eng: str, sel: str, r: Dict[str, Any]) -> str:
    return (
        f"| {eng} | {sel} | {r['n']} | {_wlp(r)} | {_pct(r.get('hit_rate'))} | {_ci(r)} | "
        f"{r['units']:+.1f} | {_roi(r)} |"
    )


def render_markdown(report: Dict[str, Any]) -> str:
    """The owner-facing report body."""
    rep = report
    eng = rep["engines"]
    inc = eng["incumbent"]
    how = " — how production refits it" if rep["bv_train_seasons"] == "all" else ""
    mk = rep["market"]["all"]
    L: List[str] = [
        f"# Residual engine gate — walk-forward, test season {rep['test_season']}",
        "",
        f"Residual engine trained on the {'/'.join(str(s) for s in rep['train_seasons'])} real-close "
        f"rows; incumbent trained on {inc['train_rows_are']} ({inc['train_seasons'][0]}-"
        f"{inc['train_seasons'][-1]}{how}; `--bv-train-seasons {rep['bv_train_seasons']}`). "
        f"Universe: {rep['n_test']} of {rep['n_test_played']} played {rep['test_season']} games "
        f"with a us-region consensus 1H close inside {rep['close_window_h']:g} h of kickoff and a "
        f"trusted 1H actual. Under at {rep['under_price']}, graded at that close.",
        "",
        "## Market benchmark",
        "",
        f"- **Close MAE vs actual: {_num(rep['close_mae'], '{:.2f}')} pts** — the benchmark. "
        "An engine that does not beat it adds nothing over reading the line.",
        f"- Blanket under at the close: {_wlp(mk)} over {mk['n']} games, {_pct(mk.get('hit_rate'))} "
        f"(95% CI {_ci(mk)}), {mk['units']:+.1f} units, ROI {_roi(mk)}.",
        "",
        "## Records (under at the close, -110)",
        "",
        "| Engine | Selection | n | W-L(-P) | Hit % | 95% CI | Units | ROI |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in ENGINES:
        if e not in eng:
            continue
        for sel in SELECTIONS:
            L.append(_rec_row(e, sel, eng[e]["selections"][sel]))
    L += [
        "",
        "## Accuracy",
        "",
        "| Engine | MAE (pts) | MAE − close MAE | Bias train (actual − pred) | Bias test | n train | n pred |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in ENGINES:
        if e not in eng:
            continue
        r = eng[e]
        L.append(
            f"| {e} | {_num(r['mae'], '{:.2f}')} | {_num(r['mae_minus_close'])} | "
            f"{_num(r['bias_train'])} | {_num(r['bias_test'])} | "
            f"{r['n_train'] if r['n_train'] is not None else '—'} | {r['n_pred']} |"
        )
    L += ["", "## Calibration by gap band (actual − prediction)", ""]
    for e in ENGINES:
        if e not in eng:
            continue
        L += [f"**{e}**", "", "| Gap band | n | Mean residual | Hit % |", "|---|---|---|---|"]
        for c in eng[e]["calibration"]:
            L.append(
                f"| {c['band']} | {c['n']} | {_num(c['mean_resid'])} | {_pct(c['hit_rate'])} |"
            )
        L.append("")
    L += [
        "## Overlap of pick sets",
        "",
        "| Selection | A | B | Both | Only A | Only B | n A | n B | Jaccard |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for sel, o in rep["overlap"].items():
        L.append(
            f"| {sel} | {o['a']} | {o['b']} | {o['both']} | {o['only_a']} | {o['only_b']} | "
            f"{o['n_a']} | {o['n_b']} | {_num(o['jaccard'], '{:.2f}')} |"
        )
    if rep.get("overlap_vs_stored"):
        for sel, o in rep["overlap_vs_stored"].items():
            L.append(
                f"| {sel} | {o['a']} | {o['b']} | {o['both']} | {o['only_a']} | {o['only_b']} | "
                f"{o['n_a']} | {o['n_b']} | {_num(o['jaccard'], '{:.2f}')} |"
            )
    fp, ifp = rep["fingerprint"], rep["incumbent_fingerprint"]
    L += [
        "",
        "## Fingerprint",
        "",
        f"- residual: `{fp['model_version']}` · {fp['n_rows']} rows · seasons {fp['seasons']} · "
        f"games {fp['min_game_date']} → {fp['max_game_date']} · {fp['n_features']} features "
        f"(hash `{fp['feature_hash']}`) · target mean {_num(fp['target_mean'], '{:+.3f}')}, "
        f"sd {_num(fp['target_std'], '{:.3f}')} · sklearn {fp['sklearn_version']}"
        + (f" · MISSING {fp['missing_features']}" if fp.get("missing_features") else ""),
        f"- incumbent: `{ifp['model_version']}` · {ifp['n_rows']} rows · seasons "
        f"{ifp['seasons'][0]}-{ifp['seasons'][-1]} · games {ifp['min_game_date']} → "
        f"{ifp['max_game_date']} · {ifp['n_features']} features (hash `{ifp['feature_hash']}`)",
        "",
        "## Caveats",
        "",
    ]
    L += [f"- {c}" for c in rep["caveats"]]
    L.append("")
    L.append(f"_Generated {rep['generated_at']} by `scripts/residual_gate.py`._")
    return "\n".join(L)
