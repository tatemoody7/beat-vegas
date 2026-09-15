"""H6 -- "when to bet": which of the four decision builds gives the best line value?

Pure arithmetic over the (build, game) rows from beatvegas/snapshots.py; the CLI is
scripts/when_to_bet_study.py. Registry row H6 in docs/HYPOTHESES.md.

Two kinds of output, deliberately kept apart:

* Weekly runs are DESCRIPTIVE. Per (week, slot, tier): how many games, how they did
  at Hard Rock's number, the price paid, and the line value against Hard Rock's own
  close and against the consensus close. The builds do not BET the same games, so
  per-build means are unpaired and say so. No verdict word is printed.
* ONE confirmatory look, on or after CONFIRMATORY_DATE (after the 2026 regular
  season): on MATCHED games (BET by both builds of a pair), the paired difference in
  favourable line value vs Hard Rock's close, paired bootstrap, Holm across the six
  pairwise comparisons of the four decision builds at family alpha 0.05, each pair
  n >= MIN_MATCHED. A build is "best" only if it beats every other build after
  correction. Otherwise NO BUILD PREFERRED. The rule was written before the numbers
  were read (2026-09-15).

Line value here is FAVOURABLE line value: the build's Hard Rock line minus the close,
so positive means the market came toward the under we would have bet. The stored
`clv_under` convention is the opposite sign (closing - bet); see grading.clv_under.
"""

from __future__ import annotations

from datetime import date
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..grading import american_to_decimal, clv_under, under_result, units_won
from ..snapshots import FOUR_BUILD_SLOTS
from .censoring import wilson
from .stats import holm_adjust, paired_bootstrap_mean

CONFIRMATORY_DATE = date(2026, 12, 7)  # the Monday after the 2026 regular season
MIN_MATCHED = 20
FAMILY_ALPHA = 0.05
TIERS = ("BET", "EDGE")
ALL_PRICED = "ALL priced"  # every Hard-Rock-priced item whatever its tier

RULE = (
    "PRE-REGISTERED (docs/HYPOTHESES.md H6, 2026-09-15): weekly runs are descriptive "
    "only. One confirmatory look on or after 2026-12-07: matched games (BET by both "
    "builds), paired difference in favourable line value vs Hard Rock's close, paired "
    "bootstrap, Holm across the six pairwise comparisons of tue_pm / thu_pm / fri_pm / "
    "sat_am at family alpha 0.05, each pair n >= 20. Best = beats every other build "
    "after correction; else NO BUILD PREFERRED."
)


def favourable_clv(bet_line: Optional[float], close: Optional[float]) -> Optional[float]:
    """bet_line - close: positive = the market came toward the under."""
    if bet_line is None or close is None or pd.isna(bet_line) or pd.isna(close):
        return None
    c = clv_under(float(bet_line), float(close))
    return None if c is None else -c


def grade(df: pd.DataFrame) -> pd.DataFrame:
    """Add outcome/units at Hard Rock's number and both favourable line values.
    Rows without a Hard Rock line grade to None; rows without a result stay
    ungraded (fh None)."""
    out = df.copy()
    outcome, units, clv_hr, clv_mk = [], [], [], []
    for r in out.itertuples(index=False):
        line = None if pd.isna(r.hr_line) else float(r.hr_line)
        fh = None if pd.isna(r.fh) else float(r.fh)
        price = -110 if pd.isna(r.hr_price) else int(r.hr_price)
        if line is None or fh is None:
            outcome.append(None)
            units.append(None)
        else:
            outcome.append(under_result(fh, line))
            units.append(units_won(fh, line, price))
        clv_hr.append(favourable_clv(line, r.hr_close))
        clv_mk.append(favourable_clv(line, r.close_line))
    out["outcome_hr"] = outcome
    out["units_hr"] = units
    out["fav_clv_hr"] = clv_hr
    out["fav_clv_mk"] = clv_mk
    return out


def _clv_block(vals: pd.Series, n_boot: int) -> Dict[str, Any]:
    x = pd.to_numeric(vals, errors="coerce").dropna().to_numpy(float)
    b = paired_bootstrap_mean(x, n_boot=n_boot)
    return {"n": b["n"], "mean": b["mean"], "lo": b["lo"], "hi": b["hi"]}


def per_build(df: pd.DataFrame, n_boot: int = 2000, tiers: Sequence[str] = TIERS) -> List[Dict]:
    """Descriptive rows per (week, slot, built_at, tier). Unpaired across slots."""
    g = grade(df)
    g = g[g["hr_line"].notna()]
    # The tiered rows, plus one "ALL priced" row per build so a build that tiered
    # nothing (every week-1 card was all PASS) still appears with its record.
    tiered = g[g["tier"].isin(tiers)]
    every = g.assign(tier=ALL_PRICED)
    g = pd.concat([tiered, every], ignore_index=True)
    rows: List[Dict] = []
    keys = ["week", "card_id", "built_at", "slot", "schedule", "tier"]
    for key, sub in g.groupby(keys, sort=True, dropna=False):
        week, card_id, built_at, slot, schedule, tier = key
        graded = sub[sub["outcome_hr"].notna()]
        under = int((graded["outcome_hr"] == "under").sum())
        over = int((graded["outcome_hr"] == "over").sum())
        push = int((graded["outcome_hr"] == "push").sum())
        decided = under + over
        lo, hi = wilson(under, decided) if decided else (None, None)
        units = pd.to_numeric(graded["units_hr"], errors="coerce")
        prices = pd.to_numeric(sub["hr_price"], errors="coerce").dropna()
        # American odds do not average across the sign (+100 and -140 average to
        # -20); report the median price and the mean break-even probability.
        be = [1.0 / american_to_decimal(int(v)) for v in prices]
        rows.append(
            {
                "week": int(week) if week is not None and not pd.isna(week) else None,
                "card_id": int(card_id),
                "built_at": built_at,
                "slot": None
                if (slot is None or (isinstance(slot, float) and np.isnan(slot)))
                else slot,
                "schedule": schedule,
                "tier": tier,
                "n": int(len(sub)),
                "graded": int(len(graded)),
                "under": under,
                "over": over,
                "push": push,
                "hit": (under / decided) if decided else None,
                "hit_lo": lo,
                "hit_hi": hi,
                "units": float(units.sum()) if len(units) else None,
                "units_per_bet": float(units.mean()) if len(units) else None,
                "median_price": float(prices.median()) if len(prices) else None,
                "break_even": float(np.mean(be)) if be else None,
                "clv_hr": _clv_block(sub["fav_clv_hr"], n_boot),
                "clv_mk": _clv_block(sub["fav_clv_mk"], n_boot),
            }
        )
    return rows


def first_qualified(df: pd.DataFrame) -> pd.DataFrame:
    """Per game ever tiered BET: the first build (built_at, slot) that did so, how
    many builds carried it as BET, and the Hard Rock line at that first build."""
    b = df[(df["tier"] == "BET") & df["hr_line"].notna()].sort_values("built_at")
    if b.empty:
        return pd.DataFrame(
            columns=[
                "game_id",
                "week",
                "first_built_at",
                "first_slot",
                "n_builds_bet",
                "first_hr_line",
            ]
        )
    first = b.groupby("game_id", sort=False).head(1)
    counts = b.groupby("game_id").size()
    out = first[["game_id", "week", "built_at", "slot", "hr_line"]].rename(
        columns={"built_at": "first_built_at", "slot": "first_slot", "hr_line": "first_hr_line"}
    )
    out["n_builds_bet"] = out["game_id"].map(counts).astype(int)
    return out.reset_index(drop=True)


def _last_build_per_week_slot(df: pd.DataFrame) -> pd.DataFrame:
    """For slots that built more than once in a week, the last build stands."""
    last = df.groupby(["week", "slot"])["built_at"].transform("max")
    return df[df["built_at"] == last]


def matched_pairs(
    df: pd.DataFrame, slot_a: str, slot_b: str, tier: str = "BET", min_week: int = 2
) -> pd.DataFrame:
    """Games tiered `tier` by BOTH slots in the same week (weeks >= min_week), one
    row per game with each slot's favourable line value vs Hard Rock's close."""
    g = grade(df)
    g = g[(g["tier"] == tier) & g["hr_line"].notna() & (g["week"] >= min_week)]
    g = _last_build_per_week_slot(g)
    a = g[g["slot"] == slot_a][["week", "game_id", "fav_clv_hr", "units_hr"]]
    b = g[g["slot"] == slot_b][["week", "game_id", "fav_clv_hr", "units_hr"]]
    m = a.merge(b, on=["week", "game_id"], suffixes=(f"_{slot_a}", f"_{slot_b}"))
    return m.dropna(subset=[f"fav_clv_hr_{slot_a}", f"fav_clv_hr_{slot_b}"]).reset_index(drop=True)


def confirmatory(
    df: pd.DataFrame,
    slots: Sequence[str] = FOUR_BUILD_SLOTS,
    n_boot: int = 2000,
    min_n: int = MIN_MATCHED,
    alpha: float = FAMILY_ALPHA,
    today: Optional[date] = None,
    earliest: date = CONFIRMATORY_DATE,
) -> Dict[str, Any]:
    """The one pre-registered test. Refuses to run before `earliest`."""
    today = today or date.today()
    if today < earliest:
        return {
            "ran": False,
            "verdict": "NOT YET EVALUABLE",
            "reasons": [f"confirmatory look is dated {earliest.isoformat()}; today is {today}"],
            "pairs": [],
            "rule": RULE,
        }
    pairs: List[Dict[str, Any]] = []
    for a, b in combinations(slots, 2):
        m = matched_pairs(df, a, b)
        x = m[f"fav_clv_hr_{a}"].to_numpy(float) if len(m) else np.array([])
        y = m[f"fav_clv_hr_{b}"].to_numpy(float) if len(m) else np.array([])
        boot = paired_bootstrap_mean(x, y, n_boot=n_boot) if len(m) else None
        pairs.append(
            {
                "a": a,
                "b": b,
                "n": int(len(m)),
                "mean_diff": None if boot is None else boot["mean"],
                "lo": None if boot is None else boot["lo"],
                "hi": None if boot is None else boot["hi"],
                "p": None if (boot is None or len(m) < min_n) else boot["p"],
            }
        )
    adj = holm_adjust([p["p"] for p in pairs])
    for p, q in zip(pairs, adj):
        p["p_holm"] = q
        p["significant"] = q is not None and q <= alpha
    reasons: List[str] = []
    thin = [f"{p['a']} vs {p['b']} (n={p['n']})" for p in pairs if p["n"] < min_n]
    if thin:
        reasons.append(f"matched n below {min_n}: " + ", ".join(thin))
    best: Optional[str] = None
    for s in slots:
        wins = 0
        for p in pairs:
            if s not in (p["a"], p["b"]) or not p["significant"]:
                continue
            diff = p["mean_diff"] if p["a"] == s else -p["mean_diff"]
            if diff is not None and diff > 0:
                wins += 1
        if wins == len(slots) - 1:
            best = s
    if best is None:
        reasons.append("no build beats every other build after Holm correction")
    return {
        "ran": True,
        "verdict": f"BEST BUILD: {best}" if best else "NO BUILD PREFERRED",
        "best": best,
        "reasons": reasons,
        "pairs": pairs,
        "alpha": alpha,
        "min_n": min_n,
        "rule": RULE,
    }


# ---------------------------------------------------------------- markdown


def _f(v: Optional[float], fmt: str = "{:+.2f}") -> str:
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else fmt.format(v)


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _ci(lo: Optional[float], hi: Optional[float], pct: bool = False) -> str:
    if lo is None or hi is None:
        return "—"
    return f"{100 * lo:.1f}–{100 * hi:.1f}%" if pct else f"{lo:+.2f}..{hi:+.2f}"


def render_markdown(r: Dict[str, Any]) -> str:
    L = [
        "# When to bet — what each build's list did at the close",
        "",
        f"Season {r['season']}, {r['n_cards']} stored builds, {r['n_rows']} (build, game) rows, "
        f"{r['n_priced']} of them Hard-Rock-priced and {r['n_graded']} graded. "
        "Line value is FAVOURABLE: the build's Hard Rock line minus the close, + = the market "
        "came toward the under. Per-build rows are unpaired — the builds do not BET the same games.",
        "",
        f"## Verdict: **{r['confirmatory']['verdict']}**",
        "",
    ]
    for why in r["confirmatory"]["reasons"] or ["every pre-registered criterion met"]:
        L.append(f"- {why}")
    L += ["", f"_{RULE}_", ""]
    L += [
        "## Per build (descriptive)",
        "",
        "| week | slot | schedule | built (UTC) | tier | n | graded | U-O-P | hit (decided) | Wilson 95% | units | median price | break-even | line value vs HR close (n) | 95% | vs consensus close (n) | 95% |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in r["per_build"]:
        ch, cm = b["clv_hr"], b["clv_mk"]
        L.append(
            f"| {b['week']} | {b['slot'] or '—'} | {b['schedule']} | {str(b['built_at'])[:16]} | {b['tier']} | {b['n']} | "
            f"{b['graded']} | {b['under']}-{b['over']}-{b['push']} | {_pct(b['hit'])} | "
            f"{_ci(b['hit_lo'], b['hit_hi'], pct=True)} | {_f(b['units'])} | {_f(b['median_price'], '{:+.0f}')} | {_pct(b['break_even'])} | "
            f"{_f(ch['mean'])} ({ch['n']}) | {_ci(ch['lo'], ch['hi'])} | {_f(cm['mean'])} ({cm['n']}) | {_ci(cm['lo'], cm['hi'])} |"
        )
    L += ["", "## First build to call each BET", ""]
    fq = r["first_qualified"]
    if fq:
        L += [
            "| week | game | first build | slot | builds as BET | HR line then |",
            "|---|---|---|---|---|---|",
        ]
        for q in fq:
            L.append(
                f"| {q['week']} | {q['game_id']} | {str(q['first_built_at'])[:16]} | {q['first_slot']} | "
                f"{q['n_builds_bet']} | {_f(q['first_hr_line'], '{:.1f}')} |"
            )
        counts: Dict[str, int] = {}
        for q in fq:
            counts[str(q["first_slot"])] = counts.get(str(q["first_slot"]), 0) + 1
        L += [
            "",
            "First-to-call counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
            "",
        ]
    else:
        L += ["No game has been tiered BET yet.", ""]
    L += ["## Matched-game pairs (the confirmatory family)", ""]
    pairs = r["confirmatory"]["pairs"]
    if pairs:
        L += [
            "| a | b | matched n | mean diff (a − b) | 95% | p | Holm p | significant |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for p in pairs:
            L.append(
                f"| {p['a']} | {p['b']} | {p['n']} | {_f(p['mean_diff'])} | {_ci(p['lo'], p['hi'])} | "
                f"{_f(p.get('p'), '{:.3f}')} | {_f(p.get('p_holm'), '{:.3f}')} | {'yes' if p.get('significant') else 'no'} |"
            )
    else:
        L.append("Not run: the confirmatory look is dated " + CONFIRMATORY_DATE.isoformat() + ".")
    L += ["", f"Generated {r['generated_at']}.", ""]
    return "\n".join(L)
