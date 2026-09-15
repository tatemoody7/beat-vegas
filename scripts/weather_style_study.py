#!/usr/bin/env python
"""Weather x offensive style, on decision-safe forecasts only.

    PYTHONPATH=. python scripts/weather_style_study.py --out reports/weather_style --n-boot 2000

Reads Neon (postmortem_games, odds_snapshots for the closing price, weather_obs,
fh_team_game, games); writes a report under reports/ (gitignored); spends nothing.
The book's de-vigged closing probability comes from the censoring study's loader
so the two studies mean the same thing by "the close".
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from beatvegas.backtest import weather_style as W
from beatvegas.db.store import session_scope, try_init_db

_ROOT = Path(__file__).resolve().parent


def _censoring_loader():
    spec = importlib.util.spec_from_file_location("censoring_study", _ROOT / "censoring_study.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_frame


def load(lead_hours: int, seasons=(2024, 2025)):
    base = (
        _censoring_loader()()
    )  # game_id, season, week, line_real, outcome_real, fh, spread..., fair_under
    base = base[base["season"].isin(seasons)].copy()
    with session_scope() as s:
        games = pd.DataFrame(
            s.execute(
                text(
                    "select id as game_id, home_team, away_team from games where season = any(:seasons)"
                ),
                {"seasons": list(seasons)},
            )
            .mappings()
            .all()
        )
        wx = pd.DataFrame(
            s.execute(
                text(
                    """
                select game_id, wind_gust_mph as gust, wind_mph as wind, temperature_f as temp,
                       precipitation as precip, dome
                from weather_obs where lead_hours = :lead and decision_safe
                """
                ),
                {"lead": lead_hours},
            )
            .mappings()
            .all()
        )
        fh = pd.DataFrame(
            s.execute(
                text(
                    "select season, week, off_team, pass_rate, explosive from fh_team_game where season = any(:seasons)"
                ),
                {"seasons": list(seasons)},
            )
            .mappings()
            .all()
        )
        fbs = pd.DataFrame(
            s.execute(
                text(
                    "select game_id from postmortem_games where scope='hist_2023_25' and division='fbs' "
                    "and run_id=(select run_id from postmortem_runs where scope='hist_2023_25' order by computed_at desc limit 1)"
                )
            )
            .mappings()
            .all()
        )
    df = base.merge(games, on="game_id", how="inner").merge(wx, on="game_id", how="inner")
    df = df[df["game_id"].isin(set(fbs["game_id"]))]
    df = df[~df["dome"].fillna(False).astype(bool)]
    for c in ("gust", "wind", "temp", "precip", "fair_under"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["gust", "fair_under"])
    df["outcome"] = df["outcome_real"].astype(str).str.lower()
    df = W.attach_style(df, fh)
    df = df.dropna(subset=["pass_rate_asof"])
    return W.flag_pass_heavy(df)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="reports/weather_style")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--lead", type=int, default=24, choices=(24, 72))
    args = ap.parse_args()
    if not try_init_db():
        print("[weather_style] DB unreachable — skipped.")
        return
    df = load(args.lead)
    fit = W.interaction_fit(df, n_boot=args.n_boot)
    seasons = W.per_season(df)
    r = {
        "lead_hours": args.lead,
        "n": int((df["outcome"].isin(["under", "over"])).sum()),
        "pass_heavy_cut": float(df.attrs["pass_heavy_cut"]),
        "buckets": W.buckets(df),
        "fit": fit,
        "per_season": seasons,
        "verdict": W.verdict(fit, seasons),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    md = W.render_markdown(r)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(f"{args.out}_{stamp}.md", "w").write(md)
    json.dump(r, open(f"{args.out}_{stamp}.json", "w"), indent=1, default=str)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(md)
    print(md)
    print(f"wrote {args.out}_{stamp}.md")
    print("VERDICT:", "SIGNAL" if r["verdict"]["signal"] else "NO FINDING")


if __name__ == "__main__":
    main()
