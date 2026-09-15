"""Hard Rock lead/lag and first-half market microstructure — what the captured
snapshots can and cannot say.

Questions (Tate, 2026-09-15, both halves):
  (a) NUMBER LAG — when the rest of the market moves its 1H total, does Hard Rock
      move in the same capture, a later one, or not before kickoff? When Hard Rock
      sits off the consensus, does its next move close the gap?
  (b) PRICE BEFORE NUMBER — does Hard Rock shade its under price while holding the
      number, and does that predict the number moving next?
Plus the microstructure around them: how far apart the books sit and how that
tightens toward kickoff, and where Hard Rock's number closes relative to the
consensus.

GRAIN. `odds_snapshots` is written by four whole-week sweeps and 30-minute close
polls inside 75 minutes of kickoff, and a row is written only when a book's quote
CHANGES (an unchanged quote stamps `last_seen_at`). So a "capture" is a batch of
rows sharing a minute, every book's line at time t is the LAST row at or before t
(the same as-of rule `lines.as_of` uses), and lag is measurable in captures — a
day apart midweek, half an hour apart at the close — not in minutes. Every table
below says so in its n and its units. A REPORT, NOT A BET.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..devig import is_centred_quote
from ..hardrock import HR_BOOK_KEY

MIN_BOOKS = 3  # a consensus needs this many centred non-Hard-Rock books
MOVE_PTS = 0.5  # the smallest move a 1H total makes
HOURS_BANDS = [("> 72h", 72, np.inf), ("24–72h", 24, 72), ("3–24h", 3, 24), ("< 3h", 0, 3)]


def prepare(snaps: pd.DataFrame) -> pd.DataFrame:
    """Normalise a raw snapshot frame: types, batch time, centred flag, hours to kick."""
    d = snaps.copy()
    d["captured_at"] = pd.to_datetime(d["captured_at"])
    d["start_date"] = pd.to_datetime(d["start_date"])
    d["line"] = pd.to_numeric(d["line"], errors="coerce")
    d = d[d["line"].notna() & (d["captured_at"] <= d["start_date"])]
    d["t"] = d["captured_at"].dt.floor("min")
    d["book"] = d["book"].str.lower()
    d["centred"] = [
        is_centred_quote(o, u) for o, u in zip(d.get("over_price"), d.get("under_price"))
    ]
    d["hours_to_kick"] = (d["start_date"] - d["t"]).dt.total_seconds() / 3600.0
    return d.sort_values(["game_id", "t", "book"]).reset_index(drop=True)


def as_of_grid(g: pd.DataFrame) -> pd.DataFrame:
    """One game's books × capture times, each cell the book's line as of that
    time (last row at or before it). Books never seen by t stay NaN. Callers pass
    CENTRED rows only — Hard Rock included: inside 3h of kickoff most of its 1H
    quotes are off-centre ladder rungs, and a rung is not the number."""
    times = sorted(g["t"].unique())
    piv = g.pivot_table(index="t", columns="book", values="line", aggfunc="last")
    piv = piv.reindex(times).ffill()
    return piv


def _consensus(row: pd.Series, hr: str = HR_BOOK_KEY) -> Optional[float]:
    others = row.drop(labels=[hr], errors="ignore").dropna()
    if len(others) < MIN_BOOKS:
        return None
    return float(others.median())


def grain(d: pd.DataFrame) -> Dict[str, Any]:
    per_game = d.groupby("game_id")["t"].nunique()
    hr = (
        d[(d["book"] == HR_BOOK_KEY) & d["centred"]]
        .groupby("game_id")["t"]
        .agg(["min", "max", "count"])
    )
    gaps = ((hr["max"] - hr["min"]).dt.total_seconds() / 3600.0) / (hr["count"] - 1).replace(
        0, np.nan
    )
    return {
        "games": int(d["game_id"].nunique()),
        "captures_per_game_mean": float(per_game.mean()),
        "captures_per_game_max": int(per_game.max()) if len(per_game) else 0,
        "hr_rows_per_game_mean": float(hr["count"].mean()) if len(hr) else None,
        "hours_between_hr_rows_median": float(gaps.median()) if gaps.notna().any() else None,
    }


def position_table(d: pd.DataFrame) -> List[Dict[str, Any]]:
    """Hard Rock minus the centred consensus at every capture where both exist,
    and what Hard Rock did by the NEXT capture of that game."""
    rows = []
    for gid, g in d.groupby("game_id"):
        grid = as_of_grid(g[g["centred"]])
        if HR_BOOK_KEY not in grid.columns:
            continue
        times = list(grid.index)
        for i, t in enumerate(times):
            hr = grid.loc[t, HR_BOOK_KEY]
            cons = _consensus(grid.loc[t])
            if pd.isna(hr) or cons is None:
                continue
            nxt = grid.loc[times[i + 1], HR_BOOK_KEY] if i + 1 < len(times) else np.nan
            rows.append(
                {
                    "game_id": gid,
                    "t": t,
                    "hr": float(hr),
                    "cons": cons,
                    "diff": round(float(hr) - cons, 2),
                    "next_hr_move": None if pd.isna(nxt) else round(float(nxt) - float(hr), 2),
                }
            )
    return rows


def position_summary(pos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def bucket(diff: float) -> str:
        if diff <= -1:
            return "HR ≥ 1 below"
        if diff < 0:
            return "HR 0.5 below"
        if diff == 0:
            return "HR at consensus"
        if diff < 1:
            return "HR 0.5 above"
        return "HR ≥ 1 above"

    order = ["HR ≥ 1 below", "HR 0.5 below", "HR at consensus", "HR 0.5 above", "HR ≥ 1 above"]
    df = pd.DataFrame(pos)
    out = []
    if df.empty:
        return out
    df["bucket"] = df["diff"].map(bucket)
    for b in order:
        g = df[df["bucket"] == b]
        nxt = g.dropna(subset=["next_hr_move"])
        toward = nxt[(np.sign(nxt["next_hr_move"]) == -np.sign(nxt["diff"])) & (nxt["diff"] != 0)]
        out.append(
            {
                "bucket": b,
                "observations": int(len(g)),
                "with_next": int(len(nxt)),
                "share_unchanged_next": (
                    float((nxt["next_hr_move"] == 0).mean()) if len(nxt) else None
                ),
                "share_toward_consensus_next": (
                    float(len(toward) / len(nxt)) if len(nxt) else None
                ),
                "mean_next_move": float(nxt["next_hr_move"].mean()) if len(nxt) else None,
            }
        )
    return out


def who_moves_first(d: pd.DataFrame) -> Dict[str, Any]:
    """Each consensus move of >= MOVE_PTS between consecutive captures: was Hard
    Rock ALREADY on that side (it led), did it move the same way in that capture,
    in a later one before kickoff, or not at all? And the reverse: Hard Rock moves
    the consensus had not made — split into moves that open a gap (leading) and
    moves that close one (catching up)."""
    already = same = later = never = 0
    hr_leads = hr_leads_followed = hr_catches_up = 0
    for _gid, g in d.groupby("game_id"):
        grid = as_of_grid(g[g["centred"]])
        if HR_BOOK_KEY not in grid.columns:
            continue
        times = list(grid.index)
        cons = [_consensus(grid.loc[t]) for t in times]
        hr = [grid.loc[t, HR_BOOK_KEY] for t in times]
        for i in range(1, len(times)):
            if cons[i] is None or cons[i - 1] is None or pd.isna(hr[i]) or pd.isna(hr[i - 1]):
                continue
            dc = cons[i] - cons[i - 1]
            dh = float(hr[i]) - float(hr[i - 1])
            gap_before = float(hr[i - 1]) - cons[i - 1]  # + when HR sat above the consensus
            if abs(dc) >= MOVE_PTS:
                if abs(gap_before) >= MOVE_PTS and np.sign(gap_before) == np.sign(dc):
                    already += 1  # the consensus came to where Hard Rock already was
                elif abs(dh) >= MOVE_PTS and np.sign(dh) == np.sign(dc):
                    same += 1
                else:
                    followed = any(
                        (not pd.isna(hr[j]))
                        and np.sign(float(hr[j]) - float(hr[i - 1])) == np.sign(dc)
                        and abs(float(hr[j]) - float(hr[i - 1])) >= MOVE_PTS
                        for j in range(i + 1, len(times))
                    )
                    later += int(followed)
                    never += int(not followed)
            elif abs(dh) >= MOVE_PTS:
                if abs(gap_before) >= MOVE_PTS and np.sign(dh) == -np.sign(gap_before):
                    hr_catches_up += 1  # closing a gap the consensus had opened
                else:
                    hr_leads += 1
                    followed = any(
                        cons[j] is not None
                        and np.sign(cons[j] - cons[i - 1]) == np.sign(dh)
                        and abs(cons[j] - cons[i - 1]) >= MOVE_PTS
                        for j in range(i + 1, len(times))
                    )
                    hr_leads_followed += int(followed)
    return {
        "consensus_moves": already + same + later + never,
        "hr_already_there": already,
        "hr_same_capture": same,
        "hr_later_capture": later,
        "hr_never_before_kick": never,
        "hr_leads": hr_leads,
        "hr_leads_then_consensus_followed": hr_leads_followed,
        "hr_catches_up": hr_catches_up,
    }


def price_before_number(d: pd.DataFrame) -> Dict[str, Any]:
    """Hard Rock rows only. An event is a row where the under price changed while
    the number did not. Baseline: any row. Question: does the number move by the
    next Hard Rock row more often after a price-only event, and in the direction
    the price pointed (a dearer under -> the number is about to fall)?"""
    h = d[(d["book"] == HR_BOOK_KEY) & d["centred"]].sort_values(["game_id", "captured_at"]).copy()
    h["under_price"] = pd.to_numeric(h["under_price"], errors="coerce")
    h["prev_line"] = h.groupby("game_id")["line"].shift(1)
    h["prev_under"] = h.groupby("game_id")["under_price"].shift(1)
    h["next_line"] = h.groupby("game_id")["line"].shift(-1)
    h = h[h["prev_line"].notna() & h["next_line"].notna()]
    price_only = h[(h["line"] == h["prev_line"]) & (h["under_price"] != h["prev_under"])]
    moved_next = price_only["next_line"] != price_only["line"]
    # under price got dearer (more negative American) -> book wants less under money at
    # this number -> expect the number to FALL; sign(prev - cur) is + when it got dearer
    agree = np.sign(price_only["next_line"] - price_only["line"]) == -np.sign(
        price_only["prev_under"] - price_only["under_price"]
    )
    base_moved = h["next_line"] != h["line"]
    return {
        "hr_rows_with_prev_and_next": int(len(h)),
        "price_only_events": int(len(price_only)),
        "share_number_moves_next_after_price_only": float(moved_next.mean())
        if len(price_only)
        else None,
        "share_number_moves_next_baseline": float(base_moved.mean()) if len(h) else None,
        "share_direction_agrees": float(agree[moved_next].mean()) if moved_next.any() else None,
    }


def dispersion(d: pd.DataFrame) -> List[Dict[str, Any]]:
    """Within-capture spread of the centred books' lines, by hours to kickoff."""
    c = d[d["centred"] & (d["book"] != HR_BOOK_KEY)]
    out = []
    for label, lo, hi in HOURS_BANDS:
        rows = []
        for _key, g in c.groupby(["game_id", "t"]):
            grid_row = g.groupby("book")["line"].last()
            if len(grid_row) < MIN_BOOKS:
                continue
            htk = float(g["hours_to_kick"].iloc[0])
            if lo <= htk < hi:
                rows.append(
                    {
                        "range": float(grid_row.max() - grid_row.min()),
                        "std": float(grid_row.std(ddof=0)),
                    }
                )
        df = pd.DataFrame(rows)
        out.append(
            {
                "band": label,
                "captures": int(len(df)),
                "mean_range_pts": float(df["range"].mean()) if len(df) else None,
                "share_all_books_agree": float((df["range"] == 0).mean()) if len(df) else None,
                "mean_std_pts": float(df["std"].mean()) if len(df) else None,
            }
        )
    return out


def closing_position(d: pd.DataFrame) -> Dict[str, Any]:
    """Hard Rock minus the centred consensus at the LAST pre-kick capture of each game."""
    diffs = []
    for _gid, g in d.groupby("game_id"):
        grid = as_of_grid(g[g["centred"]])
        if HR_BOOK_KEY not in grid.columns or grid.empty:
            continue
        last = grid.iloc[-1]
        cons = _consensus(last)
        if cons is None or pd.isna(last[HR_BOOK_KEY]):
            continue
        diffs.append(float(last[HR_BOOK_KEY]) - cons)
    a = np.array(diffs)
    return {
        "games": int(len(a)),
        "mean_diff": float(a.mean()) if len(a) else None,
        "share_below_by_1_or_more": float((a <= -1).mean()) if len(a) else None,
        "share_at_consensus": float((a == 0).mean()) if len(a) else None,
        "share_above_by_1_or_more": float((a >= 1).mean()) if len(a) else None,
    }


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{100 * v:.0f}%"


def _plain(v: Optional[float]) -> str:
    return "—" if v is None else f"{v:.2f}"


def _num(v: Optional[float], nd: int = 2) -> str:
    return "—" if v is None else f"{v:+.{nd}f}"


def render_markdown(r: Dict[str, Any]) -> str:
    g = r["grain"]
    L = [
        "# Hard Rock lead/lag and first-half microstructure — what the snapshots can say",
        "",
        f"Season {r['season']}, weeks {r['weeks']}, `1H_total` snapshots. **{g['games']} games**, "
        f"{g['captures_per_game_mean']:.1f} captures per game on average (max {g['captures_per_game_max']}), "
        f"Hard Rock re-observed every **{g['hours_between_hr_rows_median']:.0f} hours** at the median. "
        "Lag is measured in captures at that grain, not in minutes. A report, not a bet.",
        "",
        "## (a) Number lag",
        "",
        "### Where Hard Rock sits against the centred consensus, and what it does by the next capture",
        "",
        "| Hard Rock vs consensus | observations | with a next capture | unchanged next | moved toward consensus | mean next move |",
        "|---|---|---|---|---|---|",
    ]
    for p in r["position"]:
        L.append(
            f"| {p['bucket']} | {p['observations']} | {p['with_next']} | {_pct(p['share_unchanged_next'])} | "
            f"{_pct(p['share_toward_consensus_next'])} | {_num(p['mean_next_move'])} |"
        )
    w = r["who_first"]
    L += [
        "",
        "### Who moves first (consensus moves of ≥ 0.5 between consecutive captures)",
        "",
        f"- consensus moved **{w['consensus_moves']}** times: Hard Rock was **already on that side {w['hr_already_there']}**, "
        f"moved the same way **in the same capture {w['hr_same_capture']}**, **in a later capture {w['hr_later_capture']}**, "
        f"**not before kickoff {w['hr_never_before_kick']}**",
        f"- Hard Rock moved ≥ 0.5 when the consensus did not: **led {w['hr_leads']}** times (the consensus later followed "
        f"**{w['hr_leads_then_consensus_followed']}** of them) and **caught up {w['hr_catches_up']}** times (closing a gap the market had opened)",
        "",
        "## (b) Price before number",
        "",
    ]
    p = r["price_before_number"]
    L += [
        f"- Hard Rock rows with a previous and a next row: {p['hr_rows_with_prev_and_next']}; price-only events (under price changed, number held): **{p['price_only_events']}**",
        f"- the number moved by the next Hard Rock row after a price-only event **{_pct(p['share_number_moves_next_after_price_only'])}** of the time, against a baseline of **{_pct(p['share_number_moves_next_baseline'])}** for any row",
        f"- when it did move, it moved the way the price pointed (dearer under → lower number) **{_pct(p['share_direction_agrees'])}** of the time (50% = no information)",
        "",
        "## Microstructure",
        "",
        "### How far apart the centred books sit, by hours to kickoff",
        "",
        "| hours to kick | captures | mean range (pts) | all books agree | mean std (pts) |",
        "|---|---|---|---|---|",
    ]
    for b in r["dispersion"]:
        L.append(
            f"| {b['band']} | {b['captures']} | {_plain(b['mean_range_pts'])} | "
            f"{_pct(b['share_all_books_agree'])} | {_plain(b['mean_std_pts'])} |"
        )
    c = r["closing"]
    L += [
        "",
        "### Where Hard Rock's number closes against the consensus (last pre-kick capture)",
        "",
        f"- {c['games']} games: mean Hard Rock − consensus **{_num(c['mean_diff'])}** pts; "
        f"≥ 1 below **{_pct(c['share_below_by_1_or_more'])}**, at consensus **{_pct(c['share_at_consensus'])}**, ≥ 1 above **{_pct(c['share_above_by_1_or_more'])}**",
        "",
        f"_generated {r['generated_at']}_",
        "",
    ]
    return "\n".join(L)
