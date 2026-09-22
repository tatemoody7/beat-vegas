"""H-NEGGAP-L: the negative gap band under the H-INSEASON arms' corrected level.

The champion's live negative band (Hard Rock's number BELOW our own) went over
23 of 26 times through 2026 week 3, where 2023-25 shows 52.7% over on 692
decided games (docs/TWO_SIDED.md). The champion's number also runs ~1.8 points
below the market this season (docs/MODEL_LEVEL_2026.md), so part of what sits
in its negative band today would sit on the OTHER side of zero under an
intercept estimated from the season itself. This module measures that band
under each arm's intercept, per build, from stored rows only.

MEASUREMENT ONLY -- the registry row H-NEGGAP-L has no criterion. Nothing here
reaches the card, the board, the money path or the arms' own ledger, and nothing
is written to the database. Pure functions over plain dicts; the SQL lives in
scripts/neggap_level_study.py.

Arithmetic. A card item carries the champion's `gap = line - bv_line` with
`bv_line = raw + c_prior`. An arm applies `c_t` instead, so its line is
`raw + c_t` and its gap is `gap - (c_t - c_prior)`. A MORE negative intercept
lowers the arm's number and RAISES its gap.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..challenger import PAPER_ARMS, arm_label, blend
from .censoring import wilson

CHAMPION = "champion"


def arm_gap(gap: float, c_prior: float, c_t: float) -> float:
    """The arm's gap on a game the champion read at `gap`."""
    return float(gap) - (float(c_t) - float(c_prior))


def outcome(first_half_total: Optional[float], line: Optional[float]) -> Optional[str]:
    if first_half_total is None or line is None:
        return None
    fh, ln = float(first_half_total), float(line)
    if fh < ln:
        return "under"
    if fh > ln:
        return "over"
    return "push"


def arm_intercepts(context: Optional[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """{label: c_t} for the champion and every arm at one build. `context` is
    the build's challenger row fields (`c_prior`, `c_season`, `in_season_n`);
    None means the build carried no challenger context and only the champion
    can be measured."""
    out: Dict[str, Optional[float]] = {CHAMPION: None}
    if not context or context.get("c_prior") is None:
        for k in PAPER_ARMS:
            out[arm_label(k)] = None
        return out
    c_prior = float(context["c_prior"])
    c_season = context.get("c_season")
    n = int(context.get("in_season_n") or 0)
    out[CHAMPION] = c_prior
    for k in PAPER_ARMS:
        out[arm_label(k)] = blend(c_prior, None if c_season is None else float(c_season), n, k)
    return out


def anchor_build(builds: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """One build per week: the earliest `fri_pm` build that carries challenger
    context (Friday anchors the paper ledger); else the latest build with
    context; else the latest build at all (champion-only measurement). Each
    build dict: {"built_at", "slot", "items", "context"}."""
    if not builds:
        return None
    ordered = sorted(builds, key=lambda b: b["built_at"])
    with_ctx = [b for b in ordered if b.get("context")]
    fri = [b for b in with_ctx if b.get("slot") == "fri_pm"]
    if fri:
        return fri[0]
    if with_ctx:
        return with_ctx[-1]
    return ordered[-1]


def game_rows(build: Dict[str, Any], finals: Dict[int, Optional[float]]) -> List[Dict[str, Any]]:
    """Per Hard-Rock-priced, graded game at this build: the champion's gap, each
    arm's gap, and the outcome against Hard Rock's line as the card showed it."""
    cs = arm_intercepts(build.get("context"))
    c_prior = cs[CHAMPION]
    rows: List[Dict[str, Any]] = []
    for it in build.get("items") or []:
        if it.get("gap_basis") != "hardrock" or it.get("gap") is None or it.get("hr_line") is None:
            continue
        gid = int(it["game_id"])
        oc = outcome(finals.get(gid), it["hr_line"])
        if oc is None:
            continue
        gaps = {CHAMPION: float(it["gap"])}
        for label, c_t in cs.items():
            if label == CHAMPION:
                continue
            gaps[label] = (
                None if (c_t is None or c_prior is None) else arm_gap(it["gap"], c_prior, c_t)
            )
        rows.append(
            {
                "game_id": gid,
                "week": build.get("week"),
                "away": it.get("away"),
                "home": it.get("home"),
                "hr_line": float(it["hr_line"]),
                "outcome": oc,
                "gaps": gaps,
            }
        )
    return rows


def band_counts(rows: Iterable[Dict[str, Any]], label: str) -> Dict[str, Any]:
    """Negative-gap games under `label`'s gap: counts, over rate among decided
    games, Wilson 95%."""
    neg = [r for r in rows if r["gaps"].get(label) is not None and r["gaps"][label] < 0]
    over = sum(1 for r in neg if r["outcome"] == "over")
    under = sum(1 for r in neg if r["outcome"] == "under")
    push = sum(1 for r in neg if r["outcome"] == "push")
    dec = over + under
    lo, hi = wilson(over, dec)
    return {
        "label": label,
        "n": len(neg),
        "over": over,
        "under": under,
        "push": push,
        "over_rate": (over / dec) if dec else None,
        "over_ci": (lo, hi),
        "measured": any(r["gaps"].get(label) is not None for r in rows),
    }


def flips(rows: Iterable[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    """Games on a different side of zero under `label` than under the champion
    -- the flip IS the question the row asks."""
    out = []
    for r in rows:
        g = r["gaps"].get(label)
        if g is None:
            continue
        champ_neg, arm_neg = r["gaps"][CHAMPION] < 0, g < 0
        if champ_neg != arm_neg:
            out.append(
                {
                    "game_id": r["game_id"],
                    "week": r["week"],
                    "matchup": f"{r['away']} @ {r['home']}",
                    "champion_gap": round(r["gaps"][CHAMPION], 2),
                    "arm_gap": round(g, 2),
                    "outcome": r["outcome"],
                }
            )
    return out


def evaluate(
    weeks: Dict[int, Sequence[Dict[str, Any]]], finals: Dict[int, Optional[float]]
) -> Dict[str, Any]:
    """`weeks`: {week: [build, ...]} for one season. Picks each week's anchor
    build, pools the rows, and reports the negative band for the champion and
    every arm, plus the flips."""
    labels = [CHAMPION] + [arm_label(k) for k in PAPER_ARMS]
    per_week: Dict[int, Dict[str, Any]] = {}
    pooled: List[Dict[str, Any]] = []
    for wk in sorted(weeks):
        b = anchor_build(weeks[wk])
        if b is None:
            continue
        b = dict(b, week=wk)
        rows = game_rows(b, finals)
        pooled.extend(rows)
        per_week[wk] = {
            "built_at": str(b.get("built_at")),
            "slot": b.get("slot"),
            "has_context": bool(b.get("context")),
            "context": b.get("context"),
            "n_games": len(rows),
            "bands": {lb: band_counts(rows, lb) for lb in labels},
        }
    return {
        "labels": labels,
        "weeks": per_week,
        "pooled": {lb: band_counts(pooled, lb) for lb in labels},
        "flips": {lb: flips(pooled, lb) for lb in labels if lb != CHAMPION},
        "n_games": len(pooled),
        # 2023-25 real-close negative band, R07 (47.6% under, n=1,200).
        "history_over_rate": 0.524,
        "history_n": 1200,
    }


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.1f}%"


def _ci(ci) -> str:
    lo, hi = ci
    return "—" if lo is None else f"{100 * lo:.1f}–{100 * hi:.1f}%"


def render_markdown(r: Dict[str, Any]) -> str:
    L = [
        "# H-NEGGAP-L — the negative band under the arms' corrected level",
        "",
        "Measurement only. No gate, side, model or arm choice may follow from this table "
        "(registry row H-NEGGAP-L). History: 2023-25 real-close negative band went over "
        f"{_pct(r['history_over_rate'])} (n={r['history_n']:,}, R07).",
        "",
        f"Games measured (Hard-Rock-priced, graded, one anchor build per week): {r['n_games']}.",
        "",
        "| level | negative-gap games | over | under | push | over rate (decided) | Wilson 95% |",
        "|---|---|---|---|---|---|---|",
    ]
    for lb in r["labels"]:
        b = r["pooled"][lb]
        if not b["measured"]:
            L.append(f"| {lb} | — | — | — | — | not measurable (no challenger context yet) | — |")
            continue
        L.append(
            f"| {lb} | {b['n']} | {b['over']} | {b['under']} | {b['push']} | "
            f"{_pct(b['over_rate'])} | {_ci(b['over_ci'])} |"
        )
    L += [
        "",
        "## By week (anchor build)",
        "",
        "| week | build | slot | context | games | "
        + " | ".join(f"{lb} neg n / over" for lb in r["labels"])
        + " |",
        "|---|---|---|---|---|" + "---|" * len(r["labels"]),
    ]
    for wk, w in r["weeks"].items():
        cells = []
        for lb in r["labels"]:
            b = w["bands"][lb]
            cells.append("—" if not b["measured"] else f"{b['n']} / {b['over']}")
        ctx = w["context"] or {}
        ctx_s = (
            "none"
            if not w["has_context"]
            else f"n={ctx.get('in_season_n')}, c_prior={ctx.get('c_prior')}, c_season={ctx.get('c_season')}"
        )
        L.append(
            f"| {wk} | {w['built_at'][:16]} | {w['slot']} | {ctx_s} | {w['n_games']} | "
            + " | ".join(cells)
            + " |"
        )
    L += ["", "## Games that change side of zero under an arm", ""]
    any_flip = False
    for lb, fl in r["flips"].items():
        if not fl:
            continue
        any_flip = True
        L.append(f"**{lb}** ({len(fl)}):")
        L.append("")
        L.append("| week | matchup | champion gap | arm gap | outcome |")
        L.append("|---|---|---|---|---|")
        for f in fl:
            L.append(
                f"| {f['week']} | {f['matchup']} | {f['champion_gap']:+.2f} | {f['arm_gap']:+.2f} | {f['outcome']} |"
            )
        L.append("")
    if not any_flip:
        L.append("None yet.")
    return "\n".join(L) + "\n"
