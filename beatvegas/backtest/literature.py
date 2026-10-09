"""The literature looks (docs/HYPOTHESES.md, "The literature looks"; roadmap v1.3).

Three of the six one-shot history looks, each a published college-football
betting rule re-run on the seasons after the paper's own sample. Every rule
here was frozen in its registry row before this file existed (Tate's calls of
2026-10-08):

- H-LIT-ARSCOTT: the full-game OVER at the close when the expected censoring
  bias of the total exceeds 1.0 point (Arscott 2023), 2018-2025.
- H-LIT-TV: the full-game UNDER on games carried by ABC, CBS, NBC, FOX or ESPN
  (Weinbach & Paul 2009), 2013-2025.
- H-LIT-BENNETT: fade the previous season's final AP top 10 against the spread
  in its first game played (Bennett 2019), first games of 2018-2025.

Shared rules: regular season only; FBS-vs-FBS (data/fbs_teams.json); the line
is each game's median closing number across every provider CFBD `/lines` lists
for it, total and spread taken separately; pushes dropped; a one-sided exact
binomial test against 110/210 (the break-even at -110); Holm at 5% across the
six looks with m = 6 fixed, a look not yet run counting as p = 1.

Pure functions over CFBD's JSON as the API returns it (camelCase keys). The I/O
is scripts/literature_look.py. Nothing here reads the database or the model:
these looks grade a published rule at the market's own close, so the
measurement harness's frame, folds and Odds-API closes (backtest/harness.py)
do not apply; the registry gate (beatvegas/registry.py) still does.
"""

from __future__ import annotations

import statistics
from collections import Counter
from statistics import NormalDist
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ..grading import american_to_decimal
from .stats import holm_adjust

BREAK_EVEN = 110 / 210  # the win rate that breaks even at -110 (52.38%)
ALPHA = 0.05
FAMILY_M = 6  # the six v1.3 looks; fixed, whichever have run
WIN_UNITS = american_to_decimal(-110) - 1.0  # 0.909 units for a win at -110

ARSCOTT = "H-LIT-ARSCOTT"
TV = "H-LIT-TV"
BENNETT = "H-LIT-BENNETT"
# Each look's seasons (for Bennett, the seasons of the first games).
LOOKS: Dict[str, Tuple[int, int]] = {
    ARSCOTT: (2018, 2025),
    TV: (2013, 2025),
    BENNETT: (2018, 2025),
}

# Arscott's Tobit fits for the implied team scores (working paper, SSRN 4197428,
# eq. 13 and Table 5).
SIGMA_DOG = 11.280
SIGMA_FAV = 11.941
ARSCOTT_CUT = 1.00
ARSCOTT_ALT_CUT = 1.75  # the paper's in-sample alternative: descriptive only

NATIONAL_OUTLETS = frozenset({"ABC", "CBS", "NBC", "FOX", "ESPN"})
AP_POLL = "AP Top 25"
TOP_N = 10

_N = NormalDist()

WIN, LOSS, PUSH = "win", "loss", "push"


# --- the line -------------------------------------------------------------------


def median_close(
    lines: Optional[Sequence[Mapping[str, Any]]], key: str
) -> Tuple[Optional[float], int]:
    """The median of `key` (`overUnder` or `spread`) across the providers that
    carry it, and how many did. With an even count, the mean of the middle two
    (statistics.median); a provider without the number is skipped."""
    vals = [float(ln[key]) for ln in lines or () if ln.get(key) is not None]
    if not vals:
        return None, 0
    return float(statistics.median(vals)), len(vals)


# --- game filters ---------------------------------------------------------------


def played(game: Mapping[str, Any]) -> bool:
    """A game with a final score (CFBD lists cancelled and postponed games too)."""
    return bool(game.get("completed")) and (
        game.get("homePoints") is not None and game.get("awayPoints") is not None
    )


def fbs_vs_fbs(game: Mapping[str, Any], fbs: Mapping[int, Set[str]]) -> bool:
    """Both teams FBS in the game's season, per data/fbs_teams.json. A season the
    snapshot lacks raises rather than silently dropping every game of it."""
    season = int(game["season"])
    if season not in fbs:
        raise ValueError(f"data/fbs_teams.json has no season {season}")
    teams = fbs[season]
    return game.get("homeTeam") in teams and game.get("awayTeam") in teams


def regular(game: Mapping[str, Any]) -> bool:
    return (game.get("seasonType") or "regular") == "regular"


# --- grading --------------------------------------------------------------------


def total_result(points: float, line: float, side: str) -> str:
    """win / loss / push for `side` ('over' or 'under') of a full-game total."""
    if points == line:
        return PUSH
    over = points > line
    return WIN if over == (side == "over") else LOSS


def ats_result(home_points: float, away_points: float, spread: float, bet_home: bool) -> str:
    """win / loss / push against a home-relative spread (negative = home favoured,
    CFBD's sign): the home side covers when margin + spread > 0."""
    cover = (home_points - away_points) + spread
    if cover == 0:
        return PUSH
    return WIN if (cover > 0) == bet_home else LOSS


def record(results: Iterable[str]) -> Dict[str, Any]:
    """Wins, losses, pushes, the win rate with pushes dropped, the one-sided exact
    binomial p-value against BREAK_EVEN, and units at -110 (push 0, loss -1)."""
    c = Counter(results)
    w, lo, pu = c[WIN], c[LOSS], c[PUSH]
    n = w + lo
    return {
        "wins": w,
        "losses": lo,
        "pushes": pu,
        "n": n,
        "rate": (w / n) if n else None,
        "p": binomial_p(w, n),
        "units": round(w * WIN_UNITS - lo, 2),
    }


def binomial_p(wins: int, n: int, p0: float = BREAK_EVEN) -> Optional[float]:
    """P(X >= wins) for X ~ Binomial(n, p0): the one-sided exact test."""
    if n <= 0:
        return None
    from scipy.stats import binomtest

    return float(binomtest(wins, n, p0, alternative="greater").pvalue)


# --- the family -----------------------------------------------------------------


def holm_family(pvalues: Mapping[str, float], m: int = FAMILY_M) -> Dict[str, Dict[str, Any]]:
    """Holm-adjusted p-values for the looks that have run, with the family fixed
    at `m` and every look not yet run counted as p = 1. Holm is monotone in each
    p-value, so a PASS here is final. A look not passing is final when all `m`
    have run, or when its own p is at least ALPHA: Holm's loosest step tests at
    ALPHA itself, so no later rejection can bring such a look under it.
    Otherwise a later rejection can still lower its threshold."""
    ids = list(pvalues)
    if len(ids) > m:
        raise ValueError(f"{len(ids)} looks reported for a family of {m}")
    padded: List[Optional[float]] = [float(pvalues[i]) for i in ids] + [1.0] * (m - len(ids))
    adj = holm_adjust(padded)
    complete = len(ids) == m
    out: Dict[str, Dict[str, Any]] = {}
    for i, rid in enumerate(ids):
        a = float(adj[i])  # every entry is a float: none of `padded` is None
        raw = float(pvalues[rid])
        if a < ALPHA:
            verdict = "PASS"
        elif complete or raw >= ALPHA:
            verdict = "NOT MET"
        else:
            verdict = "not met so far (final once all six have run)"
        out[rid] = {"p": raw, "holm_p": a, "verdict": verdict}
    return out


# --- H-LIT-ARSCOTT --------------------------------------------------------------


def _team_bias(mu: float, sigma: float) -> float:
    """E[max(X, 0)] - mu for X ~ Normal(mu, sigma): one team's censoring bias."""
    z = mu / sigma
    return sigma * _N.pdf(z) - mu * _N.cdf(-z)


def censoring_bias(total: float, spread: float) -> Optional[float]:
    """Arscott's expected censoring bias of the total: the sum over the two teams
    of sigma*phi(mu/sigma) - mu*Phi(-mu/sigma), with the implied scores
    mu_fav = (T + S)/2 and mu_dog = (T - S)/2 (S the absolute spread) and the
    paper's sigmas. None at S = 0: no favourite to assign sigma_fav (Tate)."""
    s = abs(float(spread))
    if s == 0:
        return None
    t = float(total)
    return _team_bias((t - s) / 2, SIGMA_DOG) + _team_bias((t + s) / 2, SIGMA_FAV)


def arscott_rows(
    games: Iterable[Mapping[str, Any]],
    lines_by_id: Mapping[int, Sequence[Mapping[str, Any]]],
    fbs: Mapping[int, Set[str]],
) -> Tuple[List[Dict[str, Any]], Counter]:
    """Every graded FBS-vs-FBS regular-season game with its bias (the over at the
    median total; `qualifies` marks the tested set), and the drop counts."""
    rows: List[Dict[str, Any]] = []
    drops: Counter = Counter()
    for g in games:
        if not regular(g) or not fbs_vs_fbs(g, fbs):
            continue
        drops["universe"] += 1
        if not played(g):
            drops["not_played"] += 1
            continue
        ls = lines_by_id.get(int(g["id"]), ())
        total, n_total = median_close(ls, "overUnder")
        spread, n_spread = median_close(ls, "spread")
        if total is None or spread is None:
            drops["no_provider"] += 1
            continue
        bias = censoring_bias(total, spread)
        if bias is None:
            drops["spread_zero"] += 1
            continue
        points = float(g["homePoints"]) + float(g["awayPoints"])
        rows.append(
            {
                "season": int(g["season"]),
                "week": int(g["week"]),
                "game_id": int(g["id"]),
                "home": g["homeTeam"],
                "away": g["awayTeam"],
                "total": total,
                "spread": spread,
                "providers_total": n_total,
                "providers_spread": n_spread,
                "bias": round(bias, 4),
                "qualifies": bias > ARSCOTT_CUT,
                "qualifies_alt": bias > ARSCOTT_ALT_CUT,
                "points": points,
                "result": total_result(points, total, "over"),
            }
        )
    return rows, drops


# --- H-LIT-TV -------------------------------------------------------------------


def national_outlets(media_rows: Optional[Iterable[Mapping[str, Any]]]) -> List[str]:
    """The game's TV outlets that are exactly one of the five, case-insensitive."""
    hits = {
        (r.get("outlet") or "").strip().upper()
        for r in media_rows or ()
        if (r.get("mediaType") or "").lower() == "tv"
    }
    return sorted(hits & NATIONAL_OUTLETS)


def tv_rows(
    games: Iterable[Mapping[str, Any]],
    lines_by_id: Mapping[int, Sequence[Mapping[str, Any]]],
    media_by_id: Mapping[int, Sequence[Mapping[str, Any]]],
    fbs: Mapping[int, Set[str]],
) -> Tuple[List[Dict[str, Any]], Counter]:
    """Every graded FBS-vs-FBS regular-season game, the under at the median total,
    tagged national / other / no_media (only `national` is tested)."""
    rows: List[Dict[str, Any]] = []
    drops: Counter = Counter()
    for g in games:
        if not regular(g) or not fbs_vs_fbs(g, fbs):
            continue
        drops["universe"] += 1
        if not played(g):
            drops["not_played"] += 1
            continue
        gid = int(g["id"])
        total, n_total = median_close(lines_by_id.get(gid, ()), "overUnder")
        if total is None:
            drops["no_provider"] += 1
            continue
        media = media_by_id.get(gid)
        nets = national_outlets(media)
        group = "no_media" if not media else ("national" if nets else "other")
        points = float(g["homePoints"]) + float(g["awayPoints"])
        rows.append(
            {
                "season": int(g["season"]),
                "week": int(g["week"]),
                "game_id": gid,
                "home": g["homeTeam"],
                "away": g["awayTeam"],
                "total": total,
                "providers_total": n_total,
                "group": group,
                "networks": "+".join(nets),
                "points": points,
                "result": total_result(points, total, "under"),
            }
        )
    return rows, drops


# --- H-LIT-BENNETT --------------------------------------------------------------


def final_top10(rank_weeks: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    """{school: rank} for ranks 1-10 of the AP Top 25's final (postseason) release.
    A tie at a rank keeps every school sharing it. Empty when the poll is absent."""
    post = [w for w in rank_weeks if (w.get("seasonType") or "") == "postseason"]
    if not post:
        return {}
    last = max(post, key=lambda w: int(w.get("week") or 0))
    for poll in last.get("polls") or ():
        if poll.get("poll") == AP_POLL:
            return {
                r["school"]: int(r["rank"])
                for r in poll.get("ranks") or ()
                if r.get("rank") is not None and int(r["rank"]) <= TOP_N
            }
    return {}


def first_games_played(games: Iterable[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    """{team: its first PLAYED regular-season game}, by kickoff, any opponent
    (Tate 2026-10-08: a cancelled or postponed game is skipped)."""
    out: Dict[str, Mapping[str, Any]] = {}
    for g in sorted(
        (g for g in games if regular(g) and played(g)), key=lambda g: str(g.get("startDate") or "")
    ):
        for team in (g.get("homeTeam"), g.get("awayTeam")):
            if team and team not in out:
                out[team] = g
    return out


def bennett_rows(
    games: Iterable[Mapping[str, Any]],
    lines_by_id: Mapping[int, Sequence[Mapping[str, Any]]],
    top10: Mapping[str, int],
    fbs: Mapping[int, Set[str]],
    detail: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[List[Dict[str, Any]], Counter]:
    """One fade per previous-season top-10 team: the opponent against the median
    closing spread in that team's first game played. Drops (team-seasons):
    no game played, not FBS-vs-FBS, both teams top 10, no provider; each is
    also appended to `detail` as (team, reason) when a list is given, so a
    poll name that matches no schedule name shows in the report."""
    firsts = first_games_played(games)
    rows: List[Dict[str, Any]] = []
    drops: Counter = Counter()

    def drop(team: str, why: str) -> None:
        drops[why] += 1
        if detail is not None:
            detail.append((team, why))

    for team in sorted(top10):
        drops["universe"] += 1
        g = firsts.get(team)
        if g is None:
            drop(team, "no_game_played")
            continue
        if not fbs_vs_fbs(g, fbs):
            drop(team, "not_fbs_vs_fbs")
            continue
        team_home = g["homeTeam"] == team
        opp = g["awayTeam"] if team_home else g["homeTeam"]
        if opp in top10:
            drop(team, "both_top10")
            continue
        spread, n_spread = median_close(lines_by_id.get(int(g["id"]), ()), "spread")
        if spread is None:
            drop(team, "no_provider")
            continue
        rows.append(
            {
                "season": int(g["season"]),
                "week": int(g["week"]),
                "game_id": int(g["id"]),
                "faded": team,
                "faded_rank": int(top10[team]),
                "faded_home": team_home,
                "opponent": opp,
                "opponent_conference": (g["awayConference"] if team_home else g["homeConference"])
                or "",
                "spread": spread,
                "providers_spread": n_spread,
                "home_points": float(g["homePoints"]),
                "away_points": float(g["awayPoints"]),
                "result": ats_result(
                    float(g["homePoints"]), float(g["awayPoints"]), spread, bet_home=not team_home
                ),
            }
        )
    return rows, drops
