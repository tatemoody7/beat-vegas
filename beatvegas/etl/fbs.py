"""FBS membership by season, and the FBS-vs-FBS game filter.

The `games` table holds every game CFBD returns, including FCS / D2 / D3
matchups. From 2022 CFBD also carries betting lines for FCS games, so those rows
silently became eligible training/backtest/scoring rows (~40% of the trainable
set in 2022-25). Lower-division games score differently (1H share ~0.53-0.54 vs
~0.51 for FBS) and carry no SP+/advanced priors, so the engine must only ever
see games where BOTH teams were FBS in that season.

Membership is per season (teams move up from FCS: JMU, Sam Houston, Kennesaw
State, Delaware, Missouri State ...) and comes from CFBD `/teams/fbs?year=`,
snapshotted into the git-tracked `data/fbs_teams.json` by
`scripts/fetch_fbs_teams.py` so cloud jobs never need the API call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Set

import pandas as pd

from ..config import REPO_ROOT

FBS_TEAMS_PATH = REPO_ROOT / "data" / "fbs_teams.json"

FbsMap = Dict[int, Set[str]]


def load_fbs_teams(path: Optional[Path] = None) -> FbsMap:
    """{season: {school, ...}} from the JSON snapshot. Loud failure when the
    snapshot is missing: a silent no-filter is exactly the bug this fixes."""
    p = Path(path) if path is not None else FBS_TEAMS_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"FBS membership snapshot not found at {p}; run scripts/fetch_fbs_teams.py"
        )
    raw = json.loads(p.read_text())
    return {int(season): set(schools) for season, schools in raw.items()}


def filter_fbs_games(
    df: pd.DataFrame,
    fbs: FbsMap,
    season_col: str = "season",
    home_col: str = "home_team",
    away_col: str = "away_team",
) -> pd.DataFrame:
    """Keep only rows where both teams were FBS in that row's season.

    Raises ValueError if the frame contains a season the snapshot does not
    cover, rather than guessing (a missing season would otherwise drop every
    game of that year without a trace)."""
    if df.empty:
        return df
    seasons = set(int(s) for s in df[season_col].dropna().unique())
    missing = sorted(seasons - set(fbs))
    if missing:
        raise ValueError(
            f"fbs_teams snapshot has no entry for season(s) {missing}; "
            "re-run scripts/fetch_fbs_teams.py"
        )
    keep = [
        (h in fbs[int(s)]) and (a in fbs[int(s)])
        for s, h, a in zip(df[season_col], df[home_col], df[away_col])
    ]
    return df.loc[keep].reset_index(drop=True)
