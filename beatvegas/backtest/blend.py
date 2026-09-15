"""H3a -- the blend: what weight does the market's close deserve against our number?

    line* = w * close + (1 - w) * bv_line

One parameter, fitted by grid search to minimise MAE against the realized first-half
total on the training seasons and reported on the held-out season (2023 -> 2024,
2023-24 -> 2025). w = 1 is the close on its own, w = 0 is the market-blind bv_line;
the blend must sit between them to mean anything. Never fitted on ROI or hit rate
(docs/HYPOTHESES.md rows H3A and H3B).

The market input on 2023-25 is the CLOSING line, which contains information that did
not exist at decision time -- so the historical verdict is BLEND WINS AT CLOSE, never
"blend wins". The 2026 block uses the cards' true decision-time consensus and is
descriptive only.

Secondary diagnostics, reported and never optimised: bias by season and spread
bucket, and gate crossings at BET_GAP_PTS -- partly mechanical, because
close - line* = (1 - w)(close - bv), so a fixed 1.75 bar on the blended gap is a raw
gap of 1.75 / (1 - w). That equivalent is the honest answer to "what is bv_line for".

Spread-bucket weights are a SEPARATE pre-registered family (H3B): per held-out season,
per bucket, the paired per-game |error| difference (bucket-w minus global-w), one-sided
paired bootstrap, Holm across the four buckets; a bucket is adopted only if it passes
in both held-out seasons with n >= MIN_BUCKET_N in each, and 28+ is never adopted alone.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config import REPO_ROOT
from ..model import residual as R
from ..model.bv_line import bv_line_for_slate
from ..model.score import BET_GAP_PTS
from .stats import holm_adjust, paired_bootstrap_mean

W_STEP = 0.01
MIN_BUCKET_N = 150
FAMILY_ALPHA = 0.05
NEVER_ALONE = "28+"
BUCKETS: Tuple[Tuple[float, float, str], ...] = (
    (0.0, 14.0, "<14"),
    (14.0, 21.0, "14-21"),
    (21.0, 28.0, "21-28"),
    (28.0, math.inf, "28+"),
)
FREEZE_PATH = REPO_ROOT / "data" / "blend.json"
SPLITS: Tuple[Tuple[Tuple[int, ...], int], ...] = (((2023,), 2024), ((2023, 2024), 2025))

RULE = (
    "PRE-REGISTERED (docs/HYPOTHESES.md H3A/H3B, 2026-09-15): one global w chosen on the "
    "training seasons by MAE against the realized 1H total, reported on the held-out season "
    "for 2023->2024 and 2023-24->2025 beside w=1 (close) and w=0 (bv_line). BLEND WINS AT "
    "CLOSE only if the blend's MAE is below both arms in both held-out seasons. Bias and "
    "gate crossings are reported, never optimised. Bucket weights: paired |error| "
    "difference vs the global w, one-sided paired bootstrap, Holm across the four buckets "
    "within each held-out season at 5%, adopted only if passing in both seasons with "
    "n >= 150 each; 28+ never adopted alone. The final w is fitted once on all of 2023-25 "
    "after this evaluation and frozen in data/blend.json, read by nothing."
)


# ---------------------------------------------------------------- arithmetic


def bucket_of(spread_abs: Optional[float]) -> Optional[str]:
    if spread_abs is None or (isinstance(spread_abs, float) and math.isnan(spread_abs)):
        return None
    s = abs(float(spread_abs))
    for lo, hi, name in BUCKETS:
        if lo <= s < hi:
            return name
    return None


def blend(close: np.ndarray, bv: np.ndarray, w: float) -> np.ndarray:
    return w * np.asarray(close, float) + (1.0 - w) * np.asarray(bv, float)


def mae(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    x, y = np.asarray(a, float), np.asarray(b, float)
    m = ~(np.isnan(x) | np.isnan(y))
    return float(np.mean(np.abs(x[m] - y[m]))) if m.any() else None


def bias(pred: Sequence[float], actual: Sequence[float]) -> Optional[float]:
    x, y = np.asarray(pred, float), np.asarray(actual, float)
    m = ~(np.isnan(x) | np.isnan(y))
    return float(np.mean(x[m] - y[m])) if m.any() else None


def w_grid(step: float = W_STEP) -> np.ndarray:
    n = int(round(1.0 / step))
    return np.round(np.linspace(0.0, 1.0, n + 1), 6)


def fit_w(
    close: Sequence[float], bv: Sequence[float], actual: Sequence[float], step: float = W_STEP
) -> Dict[str, Any]:
    """Grid search for the w minimising MAE(blend, actual). Ties go to the LARGER w
    (more weight on the close -- the conservative reading of what bv_line is worth).
    Returns the chosen w, its MAE and the whole curve."""
    c, b, a = (np.asarray(v, float) for v in (close, bv, actual))
    m = ~(np.isnan(c) | np.isnan(b) | np.isnan(a))
    c, b, a = c[m], b[m], a[m]
    if len(a) == 0:
        return {"w": None, "mae": None, "n": 0, "curve": []}
    curve = [(float(w), float(np.mean(np.abs(blend(c, b, w) - a)))) for w in w_grid(step)]
    best_mae = min(v for _, v in curve)
    best_w = max(w for w, v in curve if v <= best_mae + 1e-12)
    return {"w": best_w, "mae": best_mae, "n": int(len(a)), "curve": curve}


def raw_gap_equivalent(w: Optional[float], bar: float = BET_GAP_PTS) -> Optional[float]:
    """The raw (close - bv) gap that clears `bar` on the blended gap."""
    if w is None:
        return None
    return None if w >= 1.0 else float(bar / (1.0 - w))


def gate_crossings(pg: pd.DataFrame, w: float, bar: float = BET_GAP_PTS) -> Dict[str, Any]:
    """How many test games change side of the bar when the gap is taken against
    the blend instead of bv_line. Mostly mechanical (see module docstring)."""
    raw = (pg["close"] - pg["pred_bv"]).to_numpy(float)
    before = raw >= bar
    after = (1.0 - w) * raw >= bar
    return {
        "n": int(len(pg)),
        "clear_before": int(before.sum()),
        "clear_after": int(after.sum()),
        "changed_side": int((before != after).sum()),
        "raw_gap_equivalent": raw_gap_equivalent(w, bar),
    }


# ---------------------------------------------------------------- per-game frame


def per_game_frame(
    df_played: pd.DataFrame, closes: Dict[int, float], seasons: Sequence[int]
) -> pd.DataFrame:
    """Walk-forward bv_line for every real-close game of each season in `seasons`:
    the incumbent is refit on EVERY played season before that one (as production
    does) and predicts the season's real-close rows. Rows come through
    model.residual.residual_training_frame, so the actual is the trusted first
    half and the close is inside its sane range. Columns: game_id, season, week,
    kickoff, spread_abs, bucket, close, actual, pred_bv."""
    frames: List[pd.DataFrame] = []
    for s in sorted(int(x) for x in seasons):
        train = df_played[df_played["season"] < s]
        target = R.residual_training_frame(df_played[df_played["season"] == s], closes)
        if train.empty or target.empty:
            continue
        k_train = pd.to_datetime(train["start_date"], errors="coerce")
        k_target = pd.to_datetime(target["start_date"], errors="coerce")
        if k_train.isna().any() or k_target.isna().any():
            raise ValueError(f"per_game_frame: a kickoff is missing around season {s}")
        if not k_train.max() < k_target.min():
            raise ValueError(f"per_game_frame: training kickoffs overlap season {s}")
        pred = bv_line_for_slate(train, target)
        close = target[R.LINE_COL].astype(float).to_numpy()
        actual = (target[R.TARGET].astype(float) + target[R.LINE_COL].astype(float)).to_numpy()
        spread = pd.to_numeric(target.get("spread"), errors="coerce").abs()
        frames.append(
            pd.DataFrame(
                {
                    "game_id": target["id"].astype(int).to_numpy(),
                    "season": s,
                    "week": target["week"].to_numpy(),
                    "kickoff": k_target.to_numpy(),
                    "spread_abs": spread.to_numpy(),
                    "bucket": [bucket_of(v) for v in spread],
                    "close": close,
                    "actual": actual,
                    "pred_bv": np.round(np.asarray(pred, float), 2),
                }
            )
        )
    if not frames:
        return pd.DataFrame(
            columns=[
                "game_id",
                "season",
                "week",
                "kickoff",
                "spread_abs",
                "bucket",
                "close",
                "actual",
                "pred_bv",
            ]
        )
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------- one split


def _one_sided_p(two_sided: Optional[float], mean: Optional[float]) -> Optional[float]:
    """p for H1: mean < 0, from the two-sided bootstrap p and the sign."""
    if two_sided is None or mean is None:
        return None
    return two_sided / 2.0 if mean < 0 else 1.0 - two_sided / 2.0


def evaluate_split(
    pg: pd.DataFrame, train_seasons: Sequence[int], test_season: int, n_boot: int = 2000
) -> Dict[str, Any]:
    train = pg[pg["season"].isin([int(s) for s in train_seasons])]
    test = pg[pg["season"] == int(test_season)]
    if train.empty or test.empty:
        return {
            "train_seasons": list(train_seasons),
            "test_season": int(test_season),
            "evaluated": False,
            "reason": "no rows on one side of the split",
        }
    fit = fit_w(train["close"], train["pred_bv"], train["actual"])
    w = fit["w"]
    tb = blend(test["close"].to_numpy(), test["pred_bv"].to_numpy(), w)
    out: Dict[str, Any] = {
        "train_seasons": [int(s) for s in train_seasons],
        "test_season": int(test_season),
        "evaluated": True,
        "n_train": fit["n"],
        "n_test": int(len(test)),
        "w": w,
        "train_mae_at_w": fit["mae"],
        "curve": fit["curve"],
        "test_mae": {
            "blend": mae(tb, test["actual"]),
            "close": mae(test["close"], test["actual"]),
            "bv": mae(test["pred_bv"], test["actual"]),
        },
        "test_bias": {
            "blend": bias(tb, test["actual"]),
            "close": bias(test["close"], test["actual"]),
            "bv": bias(test["pred_bv"], test["actual"]),
        },
        "crossings": gate_crossings(test, w),
    }
    # the blend against each arm, paired on the game
    e_blend = np.abs(tb - test["actual"].to_numpy())
    out["paired_vs_close"] = paired_bootstrap_mean(
        e_blend, np.abs(test["close"] - test["actual"]).to_numpy(), n_boot=n_boot
    )
    out["paired_vs_bv"] = paired_bootstrap_mean(
        e_blend, np.abs(test["pred_bv"] - test["actual"]).to_numpy(), n_boot=n_boot
    )
    # bias by bucket, three arms
    by_bucket: List[Dict[str, Any]] = []
    for _lo, _hi, name in BUCKETS:
        sub = test[test["bucket"] == name]
        if sub.empty:
            by_bucket.append({"bucket": name, "n": 0})
            continue
        sb = blend(sub["close"].to_numpy(), sub["pred_bv"].to_numpy(), w)
        by_bucket.append(
            {
                "bucket": name,
                "n": int(len(sub)),
                "bias_close": bias(sub["close"], sub["actual"]),
                "bias_bv": bias(sub["pred_bv"], sub["actual"]),
                "bias_blend": bias(sb, sub["actual"]),
                "mae_close": mae(sub["close"], sub["actual"]),
                "mae_bv": mae(sub["pred_bv"], sub["actual"]),
                "mae_blend": mae(sb, sub["actual"]),
            }
        )
    out["by_bucket"] = by_bucket
    # H3B: bucket-specific w, its own family
    rows: List[Dict[str, Any]] = []
    for _lo, _hi, name in BUCKETS:
        tr = train[train["bucket"] == name]
        te = test[test["bucket"] == name]
        row: Dict[str, Any] = {"bucket": name, "n_train": int(len(tr)), "n_test": int(len(te))}
        if tr.empty or te.empty:
            row.update({"w_bucket": None, "p": None})
            rows.append(row)
            continue
        fb = fit_w(tr["close"], tr["pred_bv"], tr["actual"])
        wb = fb["w"]
        eb = np.abs(
            blend(te["close"].to_numpy(), te["pred_bv"].to_numpy(), wb) - te["actual"].to_numpy()
        )
        eg = np.abs(
            blend(te["close"].to_numpy(), te["pred_bv"].to_numpy(), w) - te["actual"].to_numpy()
        )
        boot = paired_bootstrap_mean(eb, eg, n_boot=n_boot)
        row.update(
            {
                "w_bucket": wb,
                "mae_bucket_w": mae(eb + te["actual"].to_numpy() * 0, np.zeros(len(eb))),
                "mae_global_w": float(np.mean(eg)),
                "mean_abs_err_diff": boot["mean"],
                "lo": boot["lo"],
                "hi": boot["hi"],
                "p": _one_sided_p(boot["p"], boot["mean"]),
            }
        )
        rows.append(row)
    adj = holm_adjust([r.get("p") for r in rows])
    for r, q in zip(rows, adj):
        r["p_holm"] = q
        r["passes"] = (
            q is not None
            and q <= FAMILY_ALPHA
            and r["n_test"] >= MIN_BUCKET_N
            and r["mean_abs_err_diff"] < 0
        )
    out["buckets"] = rows
    return out


# ---------------------------------------------------------------- verdicts


def verdict(splits: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    done = [s for s in splits if s.get("evaluated")]
    if len(done) < len(splits) or not done:
        return {
            "word": "NOT EVALUATED",
            "reasons": ["a split could not be evaluated"],
            "rule": RULE,
        }
    blend_wins = all(
        s["test_mae"]["blend"] < min(s["test_mae"]["close"], s["test_mae"]["bv"]) for s in done
    )
    close_wins = all(s["test_mae"]["close"] <= s["test_mae"]["blend"] for s in done)
    reasons = [
        f"{s['train_seasons']}->{s['test_season']}: w={s['w']:.2f}, test MAE blend "
        f"{s['test_mae']['blend']:.3f} / close {s['test_mae']['close']:.3f} / bv {s['test_mae']['bv']:.3f}"
        for s in done
    ]
    if blend_wins:
        word = "BLEND WINS AT CLOSE"
    elif close_wins:
        word = "CLOSE WINS"
    else:
        word = "NO STABLE WINNER"
    return {"word": word, "reasons": reasons, "rule": RULE}


def bucket_verdict(splits: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    done = [s for s in splits if s.get("evaluated")]
    if len(done) < 2:
        return {
            "adopted": [],
            "word": "BUCKET W: NOT EVALUATED",
            "reasons": ["fewer than two splits"],
        }
    adopted: List[str] = []
    reasons: List[str] = []
    for _lo, _hi, name in BUCKETS:
        rows = [next(r for r in s["buckets"] if r["bucket"] == name) for s in done]
        passes = all(r.get("passes") for r in rows)
        if passes and name == NEVER_ALONE and len(adopted) == 0:
            reasons.append(f"{name} passed but is never adopted on its own")
            continue
        if passes:
            adopted.append(name)
        else:
            why = "; ".join(
                f"{s['test_season']}: n={r['n_test']}, Holm p={r.get('p_holm')}"
                for s, r in zip(done, rows)
            )
            reasons.append(f"{name}: not adopted ({why})")
    return {
        "adopted": adopted,
        "word": f"BUCKET W: ADOPTED {', '.join(adopted)}" if adopted else "BUCKET W: NOT ADOPTED",
        "reasons": reasons,
    }


# ---------------------------------------------------------------- freeze + live


def freeze(pg: pd.DataFrame, seasons: Sequence[int]) -> Dict[str, Any]:
    """The one final w, fitted on every real-close row of `seasons`. Written by
    the script to data/blend.json (read by nothing) only after the splits ran."""
    sub = pg[pg["season"].isin([int(s) for s in seasons])]
    fit = fit_w(sub["close"], sub["pred_bv"], sub["actual"])
    return {
        "w": fit["w"],
        "mae_at_w": fit["mae"],
        "n": fit["n"],
        "fitted_on": f"{min(seasons)}-{max(seasons)}",
        "market_input": "real 1H close (REAL_1H_CLOSE_WINDOW_H)",
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "read_by": "nothing -- measurement only (docs/HYPOTHESES.md H3A)",
    }


def write_freeze(rec: Dict[str, Any], path: Path = FREEZE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2) + "\n")
    return path


def live_frame(rows: pd.DataFrame) -> pd.DataFrame:
    """2026 decision-time rows from snapshots.build_rows: the last `final` build
    before kickoff per game with a decision-time consensus (`market_line`), a
    bv_line and a graded first half. Descriptive only, never fitted on."""
    if rows.empty:
        return pd.DataFrame(columns=["game_id", "week", "market_line", "bv_line", "fh"])
    r = rows[
        (rows["status"] == "final")
        & rows["market_line"].notna()
        & rows["bv_line"].notna()
        & rows["fh"].notna()
        & (pd.to_datetime(rows["built_at"]) < pd.to_datetime(rows["kickoff"]))
    ]
    if r.empty:
        return pd.DataFrame(columns=["game_id", "week", "market_line", "bv_line", "fh"])
    last = r.sort_values("built_at").groupby("game_id", sort=False).tail(1)
    return last[["game_id", "week", "market_line", "bv_line", "fh"]].reset_index(drop=True)


def live_summary(lf: pd.DataFrame, w: Optional[float]) -> Dict[str, Any]:
    if lf.empty or w is None:
        return {"n": int(len(lf)), "w": w, "mae": {}}
    tb = blend(lf["market_line"].to_numpy(), lf["bv_line"].to_numpy(), w)
    return {
        "n": int(len(lf)),
        "w": w,
        "mae": {
            "blend": mae(tb, lf["fh"]),
            "consensus": mae(lf["market_line"], lf["fh"]),
            "bv": mae(lf["bv_line"], lf["fh"]),
        },
        "bias": {
            "blend": bias(tb, lf["fh"]),
            "consensus": bias(lf["market_line"], lf["fh"]),
            "bv": bias(lf["bv_line"], lf["fh"]),
        },
    }


# ---------------------------------------------------------------- markdown


def _f(v: Optional[float], fmt: str = "{:.3f}") -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else fmt.format(v)


def render_markdown(r: Dict[str, Any]) -> str:
    v, bvd = r["verdict"], r["bucket_verdict"]
    L = [
        "# The blend — what weight does the close deserve against our number?",
        "",
        f"Real-close rows: {r['n_rows']} games over seasons {r['seasons']}; walk-forward bv_line "
        "refit on every prior played season. Market input on 2023-25 is the CLOSE (look-ahead "
        "relative to decision time); the 2026 block is the cards' decision-time consensus and is "
        "descriptive only.",
        "",
        f"## Verdict: **{v['word']}**",
        "",
    ]
    L += [f"- {why}" for why in v["reasons"]]
    L += ["", f"_{RULE}_", "", "## Walk-forward splits", ""]
    L += [
        "| train → test | n train | n test | w | test MAE blend | close | bv | blend−close (paired 95%) | blend−bv (paired 95%) | bias blend / close / bv | clear 1.75 before → after | changed side | raw-gap equivalent of 1.75 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in r["splits"]:
        if not s.get("evaluated"):
            L.append(
                f"| {s['train_seasons']} → {s['test_season']} | — | — | — | not evaluated: {s.get('reason')} |"
            )
            continue
        pc, pb, cr, tm, tb = (
            s["paired_vs_close"],
            s["paired_vs_bv"],
            s["crossings"],
            s["test_mae"],
            s["test_bias"],
        )
        L.append(
            f"| {s['train_seasons']} → {s['test_season']} | {s['n_train']} | {s['n_test']} | {s['w']:.2f} | "
            f"{_f(tm['blend'])} | {_f(tm['close'])} | {_f(tm['bv'])} | "
            f"{_f(pc['mean'], '{:+.3f}')} ({_f(pc['lo'], '{:+.3f}')}..{_f(pc['hi'], '{:+.3f}')}) | "
            f"{_f(pb['mean'], '{:+.3f}')} ({_f(pb['lo'], '{:+.3f}')}..{_f(pb['hi'], '{:+.3f}')}) | "
            f"{_f(tb['blend'], '{:+.2f}')} / {_f(tb['close'], '{:+.2f}')} / {_f(tb['bv'], '{:+.2f}')} | "
            f"{cr['clear_before']} → {cr['clear_after']} | {cr['changed_side']} | {_f(cr['raw_gap_equivalent'], '{:.1f}')} pts |"
        )
    L += ["", "## Bias and MAE by spread bucket (held-out seasons)", ""]
    L += [
        "| test | bucket | n | bias close / bv / blend | MAE close / bv / blend |",
        "|---|---|---|---|---|",
    ]
    for s in r["splits"]:
        for b in s.get("by_bucket", []):
            if b.get("n", 0) == 0:
                L.append(f"| {s['test_season']} | {b['bucket']} | 0 | — | — |")
                continue
            L.append(
                f"| {s['test_season']} | {b['bucket']} | {b['n']} | {_f(b['bias_close'], '{:+.2f}')} / "
                f"{_f(b['bias_bv'], '{:+.2f}')} / {_f(b['bias_blend'], '{:+.2f}')} | {_f(b['mae_close'])} / "
                f"{_f(b['mae_bv'])} / {_f(b['mae_blend'])} |"
            )
    L += ["", f"## Bucket weights (H3B, own family): **{bvd['word']}**", ""]
    L += [f"- {why}" for why in bvd["reasons"]] or ["- every bucket adopted"]
    L += [
        "",
        "| test | bucket | n train | n test | w bucket | MAE bucket-w | MAE global-w | mean |err| diff (95%) | one-sided p | Holm p | passes |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in r["splits"]:
        for b in s.get("buckets", []):
            L.append(
                f"| {s['test_season']} | {b['bucket']} | {b['n_train']} | {b['n_test']} | {_f(b.get('w_bucket'), '{:.2f}')} | "
                f"{_f(b.get('mae_bucket_w'))} | {_f(b.get('mae_global_w'))} | {_f(b.get('mean_abs_err_diff'), '{:+.3f}')} "
                f"({_f(b.get('lo'), '{:+.3f}')}..{_f(b.get('hi'), '{:+.3f}')}) | {_f(b.get('p'))} | {_f(b.get('p_holm'))} | "
                f"{'yes' if b.get('passes') else 'no'} |"
            )
    fz = r.get("freeze")
    L += ["", "## Frozen w", ""]
    if fz:
        L.append(
            f"Fitted once on all of {fz['fitted_on']} ({fz['n']} rows) after the splits above: "
            f"**w = {fz['w']:.2f}** (MAE {fz['mae_at_w']:.3f}). Written to `data/blend.json`, read by nothing."
        )
    else:
        L.append("Not frozen on this run (`--freeze` not passed).")
    lv = r.get("live")
    L += ["", "## 2026 at decision time (descriptive, never fitted on)", ""]
    if lv and lv.get("mae"):
        m, b = lv["mae"], lv["bias"]
        L.append(
            f"{lv['n']} graded games, last final build before kickoff, w = {lv['w']:.2f}: MAE blend "
            f"{_f(m['blend'])} / consensus {_f(m['consensus'])} / bv {_f(m['bv'])}; bias blend "
            f"{_f(b['blend'], '{:+.2f}')} / consensus {_f(b['consensus'], '{:+.2f}')} / bv {_f(b['bv'], '{:+.2f}')}."
        )
    else:
        L.append(f"{(lv or {}).get('n', 0)} usable rows — nothing to report.")
    L += ["", f"Generated {r['generated_at']}.", ""]
    return "\n".join(L)
