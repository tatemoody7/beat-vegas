"""Registry of candidate factors for the 1H-under ranking harness.

A Factor is one column in the feature frame plus the metadata the harness and UI
need: which family it belongs to, whether it's leak-free, whether it's derived
from a Vegas number (market), and whether it can only be known going forward
(forward_only — e.g. live injuries — so it can't be backtested historically).

Phase 1 registers the factors already computable from build_feature_frame
(the existing model features + the pace/weather display columns). Later phases
append the play-by-play-derived 1H-specific factors here; nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Optional

import pandas as pd

from ..etl.features import FH_FACTOR_COLS, MARKET_COLS, MATCHUP_COLS


@dataclass(frozen=True)
class Factor:
    name: str  # column name in the feature frame
    family: str  # grouping for the UI / reporting
    description: str = ""
    leak_free: bool = True  # uses only pre-kickoff info
    market: bool = False  # derived from a Vegas number
    forward_only: bool = False  # only knowable live; not historically backtestable
    # --- green/red factor-board display metadata (pure explainer; never ranks) ---
    direction: int = 0  # sign: direction*(value-median) > 0 => more under-favorable
    binary: bool = False  # hard green/red (dome, short week), not a tinted continuum
    hypothesis: bool = False  # unverified; rendered amber until the real ledger speaks
    tier: int = 3  # base display tier (1 proven, 2 context, 3 speculative)
    sentence: str = ""  # plain-English template for the card


# Family assignments + descriptions for the columns build_feature_frame produces.
# (market flag is applied from MARKET_COLS below so the two never drift.)
_FACTORS: List[Factor] = [
    # --- 1H / full-game scoring history (season-to-date, leak-free) ----------
    # Per-side 1H scoring levels. On the card these come with a provenance tag
    # (factors_json.fh_prior_source: season-to-date from week 3, else the prior
    # season's per-game means — see etl/context.py).
    Factor("home_fh_pf", "scoring", "Home 1H points for (per game)"),
    Factor("home_fh_pa", "scoring", "Home 1H points allowed (per game)"),
    Factor("away_fh_pf", "scoring", "Away 1H points for (per game)"),
    Factor("away_fh_pa", "scoring", "Away 1H points allowed (per game)"),
    Factor(
        "combined_fh_offense",
        "scoring",
        "Both teams' 1H offense, summed",
        tier=1,
        direction=-1,
        sentence="Both 1H offenses average {value:.1f} pts — {dir} the under.",
    ),
    Factor(
        "combined_fh_defense",
        "scoring",
        "Both teams' 1H defense, summed",
        tier=1,
        direction=-1,
        sentence="Both 1H defenses allow {value:.1f} pts — {dir} the under.",
    ),
    Factor("home_full_pf", "scoring", "Home season-to-date full-game points for"),
    Factor("home_full_pa", "scoring", "Home season-to-date full-game points allowed"),
    Factor("away_full_pf", "scoring", "Away season-to-date full-game points for"),
    Factor("away_full_pa", "scoring", "Away season-to-date full-game points allowed"),
    Factor("proj_1h_total", "scoring", "Blended projected 1H total (own off + opp def)"),
    # --- prior-season efficiency (leak-free season-1 prior) -----------------
    Factor("home_sp_off", "efficiency", "Home SP+ offense (prior season)"),
    Factor("home_sp_def", "efficiency", "Home SP+ defense (prior season)"),
    Factor("away_sp_off", "efficiency", "Away SP+ offense (prior season)"),
    Factor("away_sp_def", "efficiency", "Away SP+ defense (prior season)"),
    Factor("home_off_ppa", "efficiency", "Home offensive PPA (prior season)"),
    Factor("home_def_ppa", "efficiency", "Home defensive PPA (prior season)"),
    Factor("away_off_ppa", "efficiency", "Away offensive PPA (prior season)"),
    Factor("away_def_ppa", "efficiency", "Away defensive PPA (prior season)"),
    Factor("home_off_success", "efficiency", "Home offensive success rate (prior season)"),
    Factor("away_off_success", "efficiency", "Away offensive success rate (prior season)"),
    Factor(
        "combined_off_ppa",
        "efficiency",
        "Both offenses' PPA, summed",
        tier=1,
        direction=-1,
        sentence="Combined offensive efficiency {value:.2f} PPA — {dir} the under.",
    ),
    Factor(
        "combined_def_ppa",
        "efficiency",
        "Both defenses' PPA, summed",
        tier=1,
        direction=-1,
        sentence="Combined PPA allowed {value:.2f} — {dir} the under.",
    ),
    Factor("home_returning_ppa", "personnel", "Home returning production (PPA share)"),
    Factor("away_returning_ppa", "personnel", "Away returning production (PPA share)"),
    # --- situational (schedule-derived, leak-free) --------------------------
    # Rest / travel / kickoff carry the slow-start THESIS (early kickoffs + long
    # trips dampen first halves) but no validated real-line record: hypothesis
    # + tier 3, rendered amber until the ledger speaks. Directions are the
    # thesis sign only (travel +, earlier kickoff -); rest and tz stay 0.
    Factor(
        "home_rest_days",
        "situational",
        "Home days of rest",
        hypothesis=True,
        sentence="Home on {value:.0f} days' rest — {dir} the under.",
    ),
    Factor(
        "away_rest_days",
        "situational",
        "Away days of rest",
        hypothesis=True,
        sentence="Away on {value:.0f} days' rest — {dir} the under.",
    ),
    Factor("home_short_week", "situational", "Home on a short week (<6 days)", tier=2, binary=True),
    Factor("away_short_week", "situational", "Away on a short week (<6 days)", tier=2, binary=True),
    Factor("home_off_bye", "situational", "Home off a bye (>9 days)"),
    Factor("away_off_bye", "situational", "Away off a bye (>9 days)"),
    Factor(
        "away_travel_dist",
        "situational",
        "Away travel distance (miles)",
        direction=1,
        hypothesis=True,
        sentence="Visitors travel ~{value:.0f} miles — {dir} the under.",
    ),
    Factor(
        "away_tz_shift",
        "situational",
        "Away time-zone shift (hours)",
        hypothesis=True,
        sentence="Visitors cross {value:+.1f} time zones — {dir} the under.",
    ),
    Factor(
        "kickoff_local_hour",
        "situational",
        "Local kickoff hour",
        direction=-1,
        hypothesis=True,
        sentence="~{value:.0f}:00 local kickoff — {dir} the under.",
    ),
    Factor("early_kickoff", "situational", "Early kickoff (<=1pm local)"),
    Factor("week", "situational", "Week of season"),
    Factor("neutral_site", "situational", "Neutral-site game"),
    # --- pace (TeamRankings; historical) ------------------------------------
    Factor(
        "combined_sec_play",
        "pace",
        "Average seconds per play (both teams)",
        tier=1,
        direction=1,
        sentence="Combined pace {value:.1f}s/play — {dir} the under.",
    ),
    Factor(
        "combined_plays",
        "pace",
        "Combined plays per game (both teams)",
        tier=1,
        direction=-1,
        sentence="~{value:.0f} combined plays — {dir} the under.",
    ),
    # --- weather (Open-Meteo; partial historical coverage) ------------------
    Factor(
        "wx_temp",
        "weather",
        "Temperature (F)",
        tier=1,
        direction=-1,
        sentence="{value:.0f}°F — {dir} the under.",
    ),
    Factor(
        "wx_wind",
        "weather",
        "Wind speed (mph)",
        tier=1,
        direction=1,
        sentence="Wind {value:.0f} mph — {dir} the under (passing & kicking).",
    ),
    Factor(
        "wx_precip",
        "weather",
        "Precipitation (in)",
        tier=1,
        direction=1,
        sentence="{value:.2f}in precip — {dir} the under.",
    ),
    Factor("wx_dome", "weather", "Dome (1/0)", tier=1, binary=True, direction=-1),
    # --- schedule-derived context (offline; leak-free) ----------------------
    Factor("home_revenge", "situational", "Home lost the last meeting"),
    Factor("away_revenge", "situational", "Away lost the last meeting"),
    Factor("night_game", "situational", "Night kickoff (>=6pm local)"),
    Factor("rivalry_game", "situational", "Recurring annual rivalry matchup"),
    Factor("conference_game", "situational", "Conference matchup"),
    # --- venue (CFBD /venues; static, leak-free) ----------------------------
    Factor("venue_elevation", "venue", "Stadium elevation (m)"),
    Factor("venue_grass", "venue", "Natural grass surface (1/0)"),
    Factor("venue_capacity", "venue", "Stadium capacity"),
    # --- talent + roster experience (preseason-known; leak-free) ------------
    Factor("home_talent", "personnel", "Home talent composite"),
    Factor("away_talent", "personnel", "Away talent composite"),
    Factor("home_roster_exp", "personnel", "Home mean roster class year"),
    Factor("away_roster_exp", "personnel", "Away mean roster class year"),
    Factor("home_roster_upperclass", "personnel", "Home upperclassman share"),
    Factor("away_roster_upperclass", "personnel", "Away upperclassman share"),
    # --- regime --------------------------------------------------------------
    Factor("era_post2023", "regime", "Post-2023 running-clock era"),
    # --- market (derived from the Vegas number; not used by the BV engine) ---
    Factor("full_game_total", "market", "Vegas full-game total", market=True),
    Factor("proj_1h_ratio", "market", "Projected 1H / full-game ratio", market=True),
]


# First-half PBP factors (Phase 2) — generated from FH_FACTOR_COLS so the
# registry can never drift from what features.py actually produces.
_FH_FAMILY = {
    "epa": "fh_efficiency",
    "success": "fh_efficiency",
    "explosive": "fh_efficiency",
    "early_success": "fh_efficiency",
    "third_conv": "fh_efficiency",
    "pass_rate": "fh_tendency",
    "n_plays": "fh_pace",
    "havoc_suffered": "fh_disruption",
    "turnovers": "fh_disruption",
    "opening_score": "fh_opening",
    "opening_3out": "fh_opening",
}
# Metrics that look like under-signal on the proxy but whose real-line link is
# unproven (corr_1h shows explosive/turnovers track MORE 1H scoring). Rendered
# amber as hypotheses until the real-line ledger overturns or confirms them.
_FH_HYPOTHESIS = {"explosive", "turnovers", "havoc_suffered", "pass_rate"}
for _name in FH_FACTOR_COLS:
    _role, _metric = _name.split("_fh_", 1)[1].split("_", 1)
    _FACTORS.append(
        Factor(
            _name,
            _FH_FAMILY.get(_metric, "fh"),
            f"1H {_role} {_metric.replace('_', ' ')} (season-to-date)",
            hypothesis=_metric in _FH_HYPOTHESIS,
        )
    )

# Matchup-interaction factors (offense edge over opposing defense).
_MM_DESC = {
    "mm_explosive_edge": "Combined explosive-play edge (offenses vs defenses)",
    "mm_epa_edge": "Combined EPA edge (offenses vs defenses)",
    "mm_success_edge": "Combined success-rate edge (offenses vs defenses)",
    "mm_pace": "Combined expected 1H pace (sum of offensive plays)",
    "mm_havoc": "Combined defensive havoc generated (both defenses)",
}
_MM_HYPOTHESIS = {"mm_explosive_edge", "mm_havoc"}
for _name in MATCHUP_COLS:
    _FACTORS.append(
        Factor(_name, "matchup", _MM_DESC.get(_name, _name), hypothesis=_name in _MM_HYPOTHESIS)
    )


def default_registry() -> List[Factor]:
    """All registered factors, with the market flag synced to MARKET_COLS."""
    out = []
    for f in _FACTORS:
        market = f.market or (f.name in MARKET_COLS)
        out.append(f if market == f.market else replace(f, market=market))
    return out


def factor_by_name(name: str) -> Optional[Factor]:
    """The registered factor with this column name (flags synced), or None."""
    for f in default_registry():
        if f.name == name:
            return f
    return None


def evaluable_factors(
    df: pd.DataFrame, include_market: bool = True, include_forward_only: bool = False
) -> List[Factor]:
    """Factors present in the frame and eligible to evaluate.

    Forward-only factors are excluded by default (no historical truth to score
    them against). Market factors are kept for univariate ranking (so we can see
    how much raw signal the line carries) but the BV engine never trains on them.
    """
    out = []
    for f in default_registry():
        if f.name not in df.columns:
            continue
        if f.forward_only and not include_forward_only:
            continue
        if f.market and not include_market:
            continue
        out.append(f)
    return out
