"""H4 -- grade the gates: what did each blocker stop, and how did those games do?

EXPLORATORY (docs/HYPOTHESES.md rows H4G, H4P, H4C). Counts, records, units and Wilson
intervals per gate; no COSTLY / PROTECTIVE call and no adoption decision may come
from this sample. The candidate criterion for a future confirmatory row is recorded in
docs/GATES.md and is not applied here.

Rows come from beatvegas/snapshots.py::build_rows. The primary cut is the LAST final
build before each game's kickoff (the state the ledger acted on -- Friday anchors),
Hard-Rock-priced games only. Every gate is judged ALONE from the item's own fields,
because the card's blocker ladder stops at the first failure and so under-counts every
later gate:

    off_market     market_line - hr_line > HR_OFF_MARKET_PTS      (card.py)
    no_fair_price  ev is None
    price          ev < BET_MIN_EV
    qb_out         the item's qb_out field (2026-09-15+); before that only the
                   stored blocker can name it -- "first-failure only, undercounted"
    early_season   games_played < MIN_GAMES_FOR_REAL_MONEY where the field exists;
                   the gate itself did not exist before the 2026-09-15 card
    cap            over_cap (6th+ BET by gap that week)
    degraded       the build's status, or a gate_blocker set by apply_degraded

"Qualifying" = has a model number, Hard Rock priced it, and hr_line - bv_line >= 1.75.
For each gate: the qualifying games it FAILS, the ones it blocked ALONE (every other
gate passed -- they would have been BETs), and the ones it PASSED, each graded at Hard
Rock's number and price with favourable line value vs Hard Rock's close.

Two alternatives ride along, measurement only: a fixed -115 price ceiling beside the
market-relative price gate (H4P), and a trust-adjusted cap ranking (H4C) --
gap x trust_bucket, trust shrunk toward 1.0 as (n*ratio + 30)/(n + 30), exactly 1.0 under
n = 10, ratio = overall MAE / bucket MAE of bv_line, measured two ways (2023-25 stored
walk-forward rows; 2026 graded rows) -- against the gap-only cap-5.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..grading import under_result, units_won
from ..model.score import (
    BET_GAP_PTS,
    BET_MIN_EV,
    HR_OFF_MARKET_PTS,
    MIN_GAMES_FOR_REAL_MONEY,
    WEEKLY_BET_CAP,
)
from .blend import bucket_of
from .censoring import wilson
from .stats import paired_bootstrap_mean
from .when_to_bet import favourable_clv

GATES = ("off_market", "no_fair_price", "price", "qb_out", "early_season", "cap", "degraded")
FIXED_CEILING = -115
WILSON_MIN_N = 30
TRUST_K = 30
TRUST_MIN_N = 10
QB_FIELD_SINCE = pd.Timestamp("2026-09-15")

STATUS = (
    "EXPLORATORY (docs/HYPOTHESES.md H4G/H4P/H4C, 2026-09-15): counts, records, units and "
    "Wilson intervals per gate. No COSTLY / PROTECTIVE call and no adoption decision from "
    "this sample; a gate verdict needs its own pre-registered prospective row. Candidate "
    "criterion for that row, recorded not applied: blocked-alone n >= 30 and a per-bet-units "
    "bootstrap bound past zero."
)


# ---------------------------------------------------------------- cuts and flags


def primary_cut(rows: pd.DataFrame) -> pd.DataFrame:
    """Last build per game before its kickoff, final or degraded status, Hard Rock
    priced. Preview builds never decided anything and are excluded."""
    if rows.empty:
        return rows.copy()
    r = rows[
        rows["status"].isin(["final", "degraded"])
        & rows["hr_line"].notna()
        & (pd.to_datetime(rows["built_at"]) < pd.to_datetime(rows["kickoff"]))
    ]
    if r.empty:
        return r.copy()
    return r.sort_values("built_at").groupby("game_id", sort=False).tail(1).reset_index(drop=True)


def _bool(v) -> bool:
    return bool(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else False


def flags(df: pd.DataFrame) -> pd.DataFrame:
    """Each gate judged alone from the item's fields, plus `qualifies` and the
    provenance of the two gates that cannot always be recomputed."""
    out = df.copy()
    hr = pd.to_numeric(out["hr_line"], errors="coerce")
    mk = pd.to_numeric(out["market_line"], errors="coerce")
    bv = pd.to_numeric(out["bv_line"], errors="coerce")
    ev = pd.to_numeric(out["ev"], errors="coerce")
    out["hr_gap"] = (hr - bv).round(2)
    out["qualifies"] = hr.notna() & bv.notna() & (out["hr_gap"] >= BET_GAP_PTS)
    out["f_off_market"] = hr.notna() & mk.notna() & ((mk - hr) > HR_OFF_MARKET_PTS)
    out["f_no_fair_price"] = hr.notna() & ev.isna()
    out["f_price"] = ev.notna() & (ev < BET_MIN_EV)
    blockers = out["blocker"].astype(object).where(out["blocker"].notna(), None)
    paper = out["paper_blocker"].astype(object).where(out["paper_blocker"].notna(), None)
    if "qb_out" in out:
        has_field = out["qb_out"].notna()
    else:
        has_field = pd.Series(False, index=out.index)
    named_qb = (blockers == "qb_out") | (paper == "qb_out")
    out["f_qb_out"] = np.where(has_field, out["qb_out"].map(_bool), named_qb)
    out["qb_out_src"] = np.where(has_field, "field", "blocker only (undercounted)")
    gp = (
        pd.to_numeric(out.get("games_played"), errors="coerce")
        if "games_played" in out
        else pd.Series(np.nan, index=out.index)
    )
    named_es = (blockers == "early_season") | (paper == "early_season")
    out["f_early_season"] = np.where(gp.notna(), gp < MIN_GAMES_FOR_REAL_MONEY, named_es)
    out["early_season_src"] = np.where(
        gp.notna(),
        "field",
        np.where(
            pd.to_datetime(out["built_at"]) < QB_FIELD_SINCE, "gate did not exist", "blocker only"
        ),
    )
    out["f_cap"] = out["over_cap"].map(_bool)
    gate_blocker = (
        out["gate_blocker"] if "gate_blocker" in out else pd.Series(None, index=out.index)
    )
    out["f_degraded"] = (out["status"] == "degraded") | gate_blocker.notna()
    out["f_fixed_ceiling"] = pd.to_numeric(out["hr_price"], errors="coerce") < FIXED_CEILING
    out["n_fails"] = sum(out[f"f_{g}"].astype(int) for g in GATES)
    return out


# ---------------------------------------------------------------- records


def record(sub: pd.DataFrame, n_boot: int = 2000) -> Dict[str, Any]:
    """Record at Hard Rock's number and price over the graded rows of `sub`."""
    graded = sub[pd.to_numeric(sub["fh"], errors="coerce").notna()]
    outcomes, units, clv = [], [], []
    for r in graded.itertuples(index=False):
        price = -110 if pd.isna(r.hr_price) else int(r.hr_price)
        outcomes.append(under_result(float(r.fh), float(r.hr_line)))
        units.append(units_won(float(r.fh), float(r.hr_line), price))
        clv.append(favourable_clv(float(r.hr_line), r.hr_close))
    under = outcomes.count("under")
    over = outcomes.count("over")
    push = outcomes.count("push")
    decided = under + over
    lo, hi = wilson(under, decided) if decided >= WILSON_MIN_N else (None, None)
    u = np.asarray(units, float)
    ub = paired_bootstrap_mean(u, n_boot=n_boot) if len(u) else None
    c = np.asarray([v for v in clv if v is not None], float)
    return {
        "n": int(len(sub)),
        "graded": int(len(graded)),
        "under": under,
        "over": over,
        "push": push,
        "hit": (under / decided) if decided else None,
        "hit_lo": lo,
        "hit_hi": hi,
        "units": float(u.sum()) if len(u) else None,
        "units_per_bet": float(u.mean()) if len(u) else None,
        "units_lo": ub["lo"] if ub else None,
        "units_hi": ub["hi"] if ub else None,
        "clv_n": int(len(c)),
        "clv_mean": float(c.mean()) if len(c) else None,
    }


def gate_records(fl: pd.DataFrame, n_boot: int = 2000) -> List[Dict[str, Any]]:
    q = fl[fl["qualifies"]]
    rows: List[Dict[str, Any]] = []
    for g in GATES:
        f = q[f"f_{g}"].astype(bool)
        others = (q["n_fails"] - f.astype(int)) > 0
        rows.append(
            {
                "gate": g,
                "fails": record(q[f], n_boot),
                "alone": record(q[f & ~others], n_boot),
                "passed": record(q[~f], n_boot),
                "note": _gate_note(g, q),
            }
        )
    return rows


def _gate_note(g: str, q: pd.DataFrame) -> Optional[str]:
    if g == "qb_out" and "qb_out_src" in q and len(q):
        n_field = int((q["qb_out_src"] == "field").sum())
        return f"{n_field} of {len(q)} qualifying rows carry the field; the rest are blocker-only (undercounted)"
    if g == "early_season" and "early_season_src" in q and len(q):
        counts = q["early_season_src"].value_counts().to_dict()
        return ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    return None


def fixed_ceiling_records(fl: pd.DataFrame, n_boot: int = 2000) -> Dict[str, Any]:
    q = fl[fl["qualifies"]]
    fx, pr = q["f_fixed_ceiling"].astype(bool), q["f_price"].astype(bool)
    return {
        "ceiling": FIXED_CEILING,
        "fails": record(q[fx], n_boot),
        "passed": record(q[~fx], n_boot),
        "both": int((fx & pr).sum()),
        "fixed_only": int((fx & ~pr).sum()),
        "price_only": int((~fx & pr).sum()),
        "neither": int((~fx & ~pr).sum()),
        "fixed_only_record": record(q[fx & ~pr], n_boot),
        "price_only_record": record(q[~fx & pr], n_boot),
    }


# ---------------------------------------------------------------- trust + cap


def trust_factors(
    resid: pd.DataFrame, k: int = TRUST_K, min_n: int = TRUST_MIN_N
) -> Dict[str, Dict[str, Any]]:
    """{bucket: {n, mae, ratio, trust}} from a frame with columns bucket, pred,
    actual. ratio = overall MAE / bucket MAE; trust = (n*ratio + k) / (n + k),
    exactly 1.0 when n < min_n."""
    r = resid.dropna(subset=["pred", "actual"])
    err = (r["pred"] - r["actual"]).abs()
    overall = float(err.mean()) if len(err) else None
    out: Dict[str, Dict[str, Any]] = {}
    for name in ("<14", "14-21", "21-28", "28+"):
        m = r["bucket"] == name
        n = int(m.sum())
        if overall is None or n == 0:
            out[name] = {"n": n, "mae": None, "ratio": None, "trust": 1.0}
            continue
        b_mae = float(err[m].mean())
        ratio = overall / b_mae if b_mae > 0 else 1.0
        trust = 1.0 if n < min_n else (n * ratio + k * 1.0) / (n + k)
        out[name] = {"n": n, "mae": b_mae, "ratio": ratio, "trust": trust}
    out["_overall_mae"] = {"n": int(len(err)), "mae": overall}
    return out


def residual_frame_2026(cut: pd.DataFrame) -> pd.DataFrame:
    """Graded 2026 rows at the primary cut: bv_line vs realized, bucketed by the
    item's spread. Not only Hard-Rock-priced games -- every graded game with a
    model number, to give the buckets what n there is."""
    r = cut[
        pd.to_numeric(cut["bv_line"], errors="coerce").notna()
        & pd.to_numeric(cut["fh"], errors="coerce").notna()
    ]
    return pd.DataFrame(
        {
            "bucket": [bucket_of(v) for v in pd.to_numeric(r["spread"], errors="coerce").abs()],
            "pred": pd.to_numeric(r["bv_line"], errors="coerce").to_numpy(),
            "actual": pd.to_numeric(r["fh"], errors="coerce").to_numpy(),
        }
    )


def residual_frame_hist(rows: pd.DataFrame) -> pd.DataFrame:
    """The 2023-25 stored walk-forward rows (snapshots.postmortem_hist_rows)."""
    if rows.empty:
        return pd.DataFrame(columns=["bucket", "pred", "actual"])
    return pd.DataFrame(
        {
            "bucket": [bucket_of(v) for v in pd.to_numeric(rows["spread_abs"], errors="coerce")],
            "pred": pd.to_numeric(rows["bv_line"], errors="coerce").to_numpy(),
            "actual": pd.to_numeric(rows["fh"], errors="coerce").to_numpy(),
        }
    )


def cap_rankings(
    cut: pd.DataFrame,
    trusts: Dict[str, Dict[str, Dict[str, Any]]],
    cap: int = WEEKLY_BET_CAP,
    n_boot: int = 2000,
) -> List[Dict[str, Any]]:
    """Per week: the card's BET rows (tier BET, no blocker -- the ranked pool)
    ranked three ways; the top `cap` of each graded at Hard Rock's number."""
    pool = cut[(cut["tier"] == "BET") & cut["blocker"].isna()].copy()
    pool["gap_num"] = pd.to_numeric(pool["gap"], errors="coerce")
    pool["bucket"] = [bucket_of(v) for v in pd.to_numeric(pool["spread"], errors="coerce").abs()]
    out: List[Dict[str, Any]] = []
    for week, wk in pool.groupby("week", sort=True):
        row: Dict[str, Any] = {"week": int(week), "pool": int(len(wk)), "rankings": {}}
        sets: Dict[str, set] = {}
        for name, tr in [("gap_only", None), *trusts.items()]:
            score = wk["gap_num"].copy()
            if tr is not None:
                score = score * pd.Series(
                    [tr.get(b, {}).get("trust", 1.0) if b else 1.0 for b in wk["bucket"]],
                    index=wk.index,
                )
            top = (
                wk.assign(_s=score)
                .sort_values(["_s", "game_id"], ascending=[False, True])
                .head(cap)
            )
            sets[name] = set(top["game_id"])
            row["rankings"][name] = {
                "games": sorted(int(g) for g in top["game_id"]),
                "record": record(top, n_boot),
            }
        base = sets.get("gap_only", set())
        row["overlap_with_gap_only"] = {
            k: len(v & base) for k, v in sets.items() if k != "gap_only"
        }
        out.append(row)
    return out


def per_build_alone(fl_all_builds: pd.DataFrame) -> List[Dict[str, Any]]:
    """Secondary cut: per build, how many qualifying games each gate blocked alone."""
    q = fl_all_builds[fl_all_builds["qualifies"]]
    rows: List[Dict[str, Any]] = []
    for key, sub in q.groupby(["week", "card_id", "built_at", "slot"], sort=True, dropna=False):
        week, card_id, built_at, slot = key
        r = {
            "week": week,
            "card_id": int(card_id),
            "built_at": built_at,
            "slot": slot,
            "qualifying": int(len(sub)),
        }
        for g in GATES:
            f = sub[f"f_{g}"].astype(bool)
            r[g] = int((f & ((sub["n_fails"] - f.astype(int)) == 0)).sum())
        r["bets"] = int((sub["n_fails"] == 0).sum())
        rows.append(r)
    return rows


# ---------------------------------------------------------------- markdown


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _f(v: Optional[float], fmt: str = "{:+.2f}") -> str:
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)


def _rec(r: Dict[str, Any]) -> str:
    wil = f" ({_pct(r['hit_lo'])}–{_pct(r['hit_hi'])})" if r["hit_lo"] is not None else ""
    return (
        f"{r['graded']}/{r['n']} · {r['under']}-{r['over']}-{r['push']} · {_pct(r['hit'])}{wil} · "
        f"{_f(r['units'])}u · LV {_f(r['clv_mean'])} ({r['clv_n']})"
    )


def render_markdown(r: Dict[str, Any]) -> str:
    L = [
        "# The gates — what each blocker stopped, and how those games did",
        "",
        f"Season {r['season']}, weeks {r['weeks']}. Primary cut: the last final build before kickoff per "
        f"game, Hard-Rock-priced — {r['n_cut']} games, {r['n_qualifying']} qualifying (gap ≥ {BET_GAP_PTS} "
        f"at Hard Rock's number), {r['n_graded']} graded. Each gate judged ALONE from the item's fields. "
        "Records at Hard Rock's number and price; LV = favourable line value vs Hard Rock's close. "
        f"Wilson intervals only at n ≥ {WILSON_MIN_N} decided.",
        "",
        f"## Status: **{r['status_word']}**",
        "",
        f"_{STATUS}_",
        "",
        "## Per gate (qualifying games)",
        "",
        "| gate | fails: graded/n · U-O-P · hit · units · LV | blocked ALONE (would have been BET) | passed | note |",
        "|---|---|---|---|---|",
    ]
    for g in r["gates"]:
        L.append(
            f"| {g['gate']} | {_rec(g['fails'])} | {_rec(g['alone'])} | {_rec(g['passed'])} | {g['note'] or ''} |"
        )
    fx = r["fixed"]
    L += [
        "",
        f"## Fixed {fx['ceiling']} ceiling beside the market-relative price gate (H4P)",
        "",
        f"Both fail {fx['both']} · fixed only {fx['fixed_only']} · price only {fx['price_only']} · neither {fx['neither']}.",
        "",
        "| set | graded/n · U-O-P · hit · units · LV |",
        "|---|---|",
        f"| fails the {fx['ceiling']} ceiling | {_rec(fx['fails'])} |",
        f"| passes it | {_rec(fx['passed'])} |",
        f"| fixed only (price gate let through) | {_rec(fx['fixed_only_record'])} |",
        f"| price only (ceiling let through) | {_rec(fx['price_only_record'])} |",
        "",
        "## Trust by spread bucket (H4C inputs)",
        "",
        "| source | bucket | n | MAE | ratio | trust |",
        "|---|---|---|---|---|---|",
    ]
    for src, tf in r["trusts"].items():
        for b in ("<14", "14-21", "21-28", "28+"):
            t = tf[b]
            L.append(
                f"| {src} | {b} | {t['n']} | {_f(t['mae'], '{:.3f}')} | {_f(t['ratio'], '{:.3f}')} | {t['trust']:.3f} |"
            )
    L += [
        "",
        "## Cap-5 three ways (H4C)",
        "",
        "| week | pool | ranking | games | graded/n · U-O-P · hit · units · LV | overlap with gap-only |",
        "|---|---|---|---|---|---|",
    ]
    for wk in r["cap"]:
        for name, rk in wk["rankings"].items():
            ov = "" if name == "gap_only" else str(wk["overlap_with_gap_only"].get(name))
            L.append(
                f"| {wk['week']} | {wk['pool']} | {name} | {', '.join(map(str, rk['games']))} | {_rec(rk['record'])} | {ov} |"
            )
    L += [
        "",
        "## Secondary: blocked-alone per build",
        "",
        "| week | slot | built (UTC) | qualifying | " + " | ".join(GATES) + " | BETs |",
        "|---|---|---|---|" + "---|" * len(GATES) + "---|",
    ]
    for b in r["per_build"]:
        L.append(
            f"| {b['week']} | {b['slot'] or '—'} | {str(b['built_at'])[:16]} | {b['qualifying']} | "
            + " | ".join(str(b[g]) for g in GATES)
            + f" | {b['bets']} |"
        )
    L += ["", f"Generated {r['generated_at']}.", ""]
    return "\n".join(L)
