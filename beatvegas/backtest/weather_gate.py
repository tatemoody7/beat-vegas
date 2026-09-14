"""What changes on the board when the model reads the REPAIRED weather.

This gate answers a narrower question than its siblings, and the difference
matters. `level_anchor` asks whether a proposed change is an improvement worth
adopting. This one does not: the weather values were WRONG -- keyed with a UTC
hour against a local-time series, so displaced by the venue's UTC offset -- and
correctness was settled against ground truth by `scripts/weather_validate.py`,
not by a backtest. What is undecided is *when* the live model starts using them,
with real money on a card.

So the pre-registered rule is about timing:

  Promote before the next card if the repaired weather moves few enough games
  across BET_GAP_PTS that every mover can be looked at individually. Otherwise
  promote after that card settles. Either way the fix lands.

DO NOT read a flat or worse MAE as a reason not to adopt. That is the documented
level-anchor trap: MAE is near-blind to changes of this kind, and a weather
feature is a small term against ~11 points of per-game spread. The numbers here
are a blast radius, not a verdict.

ARMS are weather leads, and `None` -- the legacy `weather` table -- is the
incumbent, exactly as k=0 is in the level anchor:

  None  the legacy table, wrong values, what ships today
  0     near-kickoff, repaired. Good for modelling; NEVER decision-safe.
  24/72 the forecast that genuinely existed that far ahead, 2024+ only.

An arm at lead 24 or 72 is the honest one for a market-edge study, and also the
one with no train/serve skew: the live model scores upcoming games off a forecast,
so training it on forecasts rather than on near-actuals is the like-for-like
choice. That is a separate argument from accuracy and is not settled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from ..etl.features import build_feature_frame, training_frame
from ..model.bv_line import bv_line_for_slate
from ..model.score import BET_GAP_PTS
from .level_anchor import _paired_ci
from .residual_gate import GateNotEvaluable, _bias, _clean, _mae, walk_forward_split

# None must come first: it is the incumbent every other arm is paired against.
WEATHER_ARMS: Sequence[Optional[int]] = (None, 0, 24, 72)

# More movers than this and the card cannot be eyeballed game by game, which is
# the whole content of the promote-now rule.
EYEBALLABLE_MOVERS = 5


def _tag(lead: Optional[int]) -> str:
    return "legacy" if lead is None else f"lead{lead}"


@dataclass
class WeatherGateResult:
    per_game: pd.DataFrame
    report: Dict[str, Any]


def _frames(
    arms: Sequence[Optional[int]], min_games: int, fbs_only: bool
) -> Dict[str, pd.DataFrame]:
    """One feature frame per arm. The build is the expensive step and does not
    depend on the season split, so it is done once and reused."""
    return {
        _tag(lead): build_feature_frame(min_games=min_games, fbs_only=fbs_only, weather_lead=lead)
        for lead in arms
    }


def _predict(frame: pd.DataFrame, train_seasons: Sequence[int], test_season: int) -> pd.DataFrame:
    """bv_line for one arm's test season, fitted on that arm's own train rows."""
    played = training_frame(frame)
    train, test = walk_forward_split(played, train_seasons, test_season)
    pred = bv_line_for_slate(train, test)
    return pd.DataFrame(
        {
            "id": test["id"].to_numpy(),
            "season": test["season"].to_numpy(),
            "week": test["week"].to_numpy(),
            "actual": pd.to_numeric(test["first_half_total"], errors="coerce").to_numpy(),
            "pred": np.asarray(pred, dtype=float),
        }
    ).set_index("id")


def _coverage(frame: pd.DataFrame) -> Dict[str, Any]:
    """How much of the arm's own test frame actually carries weather.

    An arm can look harmless purely because it has no data -- lead 24/72 hold
    nothing before the 2024 season -- and that must be visible next to its MAE
    rather than inferred later.
    """
    n = int(len(frame))
    have = int(pd.to_numeric(frame.get("wx_temp"), errors="coerce").notna().sum()) if n else 0
    return {"n_rows": n, "n_with_temp": have, "share": (have / n) if n else None}


def evaluate(
    train_seasons: Sequence[int],
    test_season: int,
    arms: Sequence[Optional[int]] = WEATHER_ARMS,
    min_games: int = 0,
    fbs_only: bool = True,
    frames: Optional[Dict[str, pd.DataFrame]] = None,
    closes: Optional[Dict[int, float]] = None,
) -> WeatherGateResult:
    leads = list(arms)
    if None not in leads:
        raise ValueError("the arms must contain None -- the legacy table is the incumbent")
    frames = frames or _frames(leads, min_games, fbs_only)

    preds = {_tag(x): _predict(frames[_tag(x)], train_seasons, test_season) for x in leads}
    base = preds["legacy"]
    if base.empty:
        raise GateNotEvaluable(f"no test rows for season {test_season}")

    per_game = base[["season", "week", "actual"]].copy()
    for lead in leads:
        t = _tag(lead)
        p = preds[t].reindex(base.index)
        per_game[f"pred_{t}"] = p["pred"]
        per_game[f"abserr_{t}"] = (per_game["actual"] - p["pred"]).abs()
    if closes:
        # Real captured 1H closes only -- the same cut every other conclusion in
        # this repo is drawn on. A game without one is absent from the crossing
        # count, never filled with a proxy.
        per_game["line"] = pd.Series(closes).reindex(per_game.index)

    rows: List[Dict[str, Any]] = []
    for lead in leads:
        t = _tag(lead)
        gain = per_game["abserr_legacy"] - per_game[f"abserr_{t}"]
        row: Dict[str, Any] = {
            "lead_hours": lead,
            "arm": t,
            "is_incumbent": lead is None,
            "decision_safe": lead is not None and lead >= 24,
            "coverage": _coverage(frames[t]),
            "n": int(len(per_game)),
            "mae": _mae(per_game["actual"], per_game[f"pred_{t}"]),
            "mae_incumbent": _mae(per_game["actual"], per_game["pred_legacy"]),
            # Signed, as (prediction - actual): NEGATIVE means bv_line reads low,
            # which inflates every gap and pushes games over the bet threshold.
            "bias": _bias(per_game[f"pred_{t}"], per_game["actual"]),
            "bias_incumbent": _bias(per_game["pred_legacy"], per_game["actual"]),
            "paired_gain": _paired_ci(gain),
            "n_changed": int((gain.abs() > 1e-9).sum()),
        }
        if "line" in per_game.columns:
            priced = per_game[per_game["line"].notna()]
            gap = priced["line"] - priced[f"pred_{t}"]
            gap_base = priced["line"] - priced["pred_legacy"]
            clears, clears_base = gap >= BET_GAP_PTS, gap_base >= BET_GAP_PTS
            row["gate"] = {
                "n_priced": int(len(priced)),
                "mean_gap": float(gap.mean()) if len(priced) else None,
                "n_clearing": int(clears.sum()),
                "n_clearing_incumbent": int(clears_base.sum()),
                # The number the promote-now decision actually turns on.
                "n_crossing": int((clears != clears_base).sum()),
                "crossing_ids": [int(i) for i in priced.index[clears != clears_base]][:50],
            }
        rows.append(row)

    report = {
        "kind": "weather_gate",
        "question": "when does the repaired weather reach the live model, not whether it is correct",
        "train_seasons": [int(s) for s in train_seasons],
        "test_season": int(test_season),
        "min_games": int(min_games),
        "fbs_only": bool(fbs_only),
        "arms": [_tag(x) for x in leads],
        "bet_gap_pts": BET_GAP_PTS,
        "eyeballable_movers": EYEBALLABLE_MOVERS,
        "n_test": int(len(per_game)),
        "n_with_close": int(per_game["line"].notna().sum()) if "line" in per_game else 0,
        "results": rows,
        "caveats": _caveats(rows, test_season),
    }
    return WeatherGateResult(per_game=per_game.reset_index(), report=_clean(report))


def _caveats(rows: List[Dict[str, Any]], test_season: int) -> List[str]:
    out: List[str] = []
    if test_season < 2024:
        out.append(
            f"test season {test_season} predates the fixed-lead data: leads 24 and 72 "
            "carry no wind, gusts or precipitation before 2024, so those arms are "
            "temperature-only here and their flatness means nothing."
        )
    for r in rows:
        cov = r["coverage"]
        if cov["share"] is not None and cov["share"] < 0.5 and r["lead_hours"] is not None:
            out.append(
                f"{r['arm']}: only {cov['share']:.0%} of rows carry a temperature "
                f"({cov['n_with_temp']}/{cov['n_rows']}) -- a flat result may be absence, not evidence."
            )
    if not any(r.get("gate", {}).get("n_priced") for r in rows):
        out.append("no real captured closes in the test season: the crossing count is unavailable.")
    out.append(
        "MAE is near-blind to a change of this kind (docs/LEVEL_ANCHOR.md). Read the "
        "crossing count and the bias, not the MAE."
    )
    return out


def render_markdown(report: Dict[str, Any]) -> str:
    L: List[str] = []
    L.append("# Weather gate — when does the repaired weather reach the live model")
    L.append("")
    L.append(
        f"Train {report['train_seasons']} → test **{report['test_season']}**, "
        f"{report['n_test']} games, {report['n_with_close']} with a real 1H close."
    )
    L.append("")
    L.append(
        "**This is not a correctness test.** The old values were wrong and the repair is "
        "verified against ground truth in `scripts/weather_validate.py`. What is open is "
        "the timing: promote before the next card only if few enough games cross "
        f"`BET_GAP_PTS` ({report['bet_gap_pts']}) that each mover can be looked at."
    )
    L.append("")
    L.append(
        "| arm | decision-safe | temp coverage | MAE | bias | games changed | clears gate | crosses |"
    )
    L.append("|---|---|---|---|---|---|---|---|")
    for r in report["results"]:
        g = r.get("gate") or {}
        cov = r["coverage"]["share"]
        L.append(
            f"| {r['arm']}{' (incumbent)' if r['is_incumbent'] else ''} "
            f"| {'yes' if r['decision_safe'] else 'no'} "
            f"| {f'{cov:.0%}' if cov is not None else '—'} "
            f"| {r['mae']:.3f} | {r['bias']:+.2f} | {r['n_changed']} "
            f"| {g.get('n_clearing', '—')} | {g.get('n_crossing', '—')} |"
        )
    L.append("")
    movers = [r for r in report["results"] if (r.get("gate") or {}).get("n_crossing") is not None]
    if movers:
        L.append("## Crossings")
        for r in movers:
            g = r["gate"]
            verdict = (
                "small enough to eyeball — promote now is defensible"
                if g["n_crossing"] <= report["eyeballable_movers"]
                else "too many to check individually — promote after the next card settles"
            )
            L.append(
                f"- **{r['arm']}**: {g['n_crossing']} of {g['n_priced']} priced games change "
                f"side of the gate ({g['n_clearing_incumbent']} → {g['n_clearing']} clearing). {verdict}"
            )
            if g["crossing_ids"]:
                L.append(f"  - game ids: {', '.join(str(i) for i in g['crossing_ids'])}")
        L.append("")
    L.append("## Caveats")
    for c in report["caveats"]:
        L.append(f"- {c}")
    return "\n".join(L) + "\n"
