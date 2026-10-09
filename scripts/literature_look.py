#!/usr/bin/env python
"""H-LIT-ARSCOTT / H-LIT-TV / H-LIT-BENNETT (docs/HYPOTHESES.md, "The literature
looks"): ONE literature look per dispatch, on CFBD data only.

    study.yml -> literature_look --row H-LIT-ARSCOTT

Refuses (exit 2) a row that is not runnable (beatvegas/registry.py), so a look
already decided cannot be run a second time. Fetches each season's
regular-season /games and /lines, plus /games/media for H-LIT-TV and the
previous season's postseason /rankings for H-LIT-BENNETT, grades the frozen
rule (beatvegas/backtest/literature.py) and writes
reports/literature_<row>_<UTC>.{md,json,csv}. READ-ONLY: no table, no Odds API
credits, no database. Exits 0 whatever the numbers say.

    literature_look --holm a.json b.json ...

combines finished looks' JSON reports into the family table (Holm at 5%,
m = 6, a look not yet run at p = 1). No CFBD call.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from beatvegas.backtest import literature as L
from beatvegas.etl.fbs import load_fbs_teams
from beatvegas.registry import HarnessRefusal, require_runnable_row

SLUG = {L.ARSCOTT: "arscott", L.TV: "tv", L.BENNETT: "bennett"}


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{100 * x:.1f}%"


def _p(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.4f}"


def _rec_line(r: Mapping[str, Any]) -> str:
    return (
        f"{r['wins']}-{r['losses']}-{r['pushes']} (n {r['n']}, {_pct(r['rate'])}), "
        f"p {_p(r['p'])}, units {r['units']:+.2f}"
    )


def tested(row_id: str, rows: Iterable[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """The rows the registered test reads."""
    if row_id == L.ARSCOTT:
        return [r for r in rows if r["qualifies"]]
    if row_id == L.TV:
        return [r for r in rows if r["group"] == "national"]
    return list(rows)


def _by(
    rows: Iterable[Mapping[str, Any]], key: Callable[[Mapping[str, Any]], Any]
) -> Dict[Any, Dict]:
    groups: Dict[Any, List[str]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r["result"])
    return {k: L.record(v) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def run_look(row_id: str, client: Any, fbs: Mapping[int, set]) -> Dict[str, Any]:
    """Fetch every season of the look, build its rows, and summarise them."""
    start, end = L.LOOKS[row_id]
    rows: List[Dict[str, Any]] = []
    drops: Counter = Counter()
    drops_by_season: Dict[int, Dict[str, int]] = {}
    providers: Dict[str, Dict[str, int]] = {}
    notes: List[str] = []
    keys = (
        ("overUnder", "spread")
        if row_id == L.ARSCOTT
        else (("overUnder",) if row_id == L.TV else ("spread",))
    )
    for season in range(start, end + 1):
        games = client.games(season, season_type="regular")
        lines_by_id = {
            int(g["id"]): (g.get("lines") or [])
            for g in client.lines(season, season_type="regular")
        }
        if row_id == L.ARSCOTT:
            got, d = L.arscott_rows(games, lines_by_id, fbs)
        elif row_id == L.TV:
            media_by_id: Dict[int, List[Mapping[str, Any]]] = defaultdict(list)
            for m in client.game_media(season, season_type="regular"):
                media_by_id[int(m["id"])].append(m)
            got, d = L.tv_rows(games, lines_by_id, media_by_id, fbs)
        else:
            top10 = L.final_top10(client.rankings(season - 1, season_type="postseason"))
            if not top10:
                notes.append(f"{season}: no final AP poll found for {season - 1}")
            detail: List[Tuple[str, str]] = []
            got, d = L.bennett_rows(games, lines_by_id, top10, fbs, detail=detail)
            notes.extend(f"{season}: {team} dropped ({why})" for team, why in detail)
        for k in keys:
            c: Counter = Counter()
            for r in got:
                for ln in lines_by_id.get(r["game_id"], ()):
                    if ln.get(k) is not None:
                        c[ln["provider"]] += 1
            providers[f"{season} {k}"] = dict(c.most_common())
        rows.extend(got)
        drops.update(d)
        drops_by_season[season] = dict(d)
        print(f"[literature] {row_id} {season}: {len(got)} graded, drops {dict(d)}")
    sel = tested(row_id, rows)
    rec = L.record(r["result"] for r in sel)
    family = L.holm_family({row_id: rec["p"]})[row_id] if rec["p"] is not None else None
    secondary: Dict[str, Any] = {}
    if row_id == L.ARSCOTT:
        secondary["alt_cut_1.75"] = L.record(r["result"] for r in rows if r["qualifies_alt"])
        secondary["qualifying_share"] = (len(sel) / len(rows)) if rows else None
        secondary["all_graded_overs"] = L.record(r["result"] for r in rows)
    elif row_id == L.TV:
        secondary["by_network"] = _by(sel, lambda r: r["networks"])
        secondary["other_tv_under"] = L.record(r["result"] for r in rows if r["group"] == "other")
        secondary["no_media_under"] = L.record(
            r["result"] for r in rows if r["group"] == "no_media"
        )
        secondary["media_coverage"] = {
            str(s): dict(Counter(r["group"] for r in rows if r["season"] == s))
            for s in range(start, end + 1)
        }
    else:
        secondary["by_opponent_conference"] = _by(
            sel, lambda r: r["opponent_conference"] or "(none)"
        )
        secondary["by_faded_home"] = _by(
            sel, lambda r: "faded at home" if r["faded_home"] else "faded away"
        )
    return {
        "row": row_id,
        "seasons": [start, end],
        "record": rec,
        "holm_alone": family,
        "by_season": _by(sel, lambda r: r["season"]),
        "drops": dict(drops),
        "drops_by_season": {str(k): v for k, v in drops_by_season.items()},
        "providers": providers,
        "secondary": secondary,
        "notes": notes,
        "rows": rows,
    }


def _md(row: Any, res: Mapping[str, Any], run_at: str, calls_left: Optional[int]) -> str:
    rec = res["record"]
    fam = res["holm_alone"]
    out = [
        f"# {res['row']} — literature look ({run_at})",
        "",
        f"Seasons {res['seasons'][0]}-{res['seasons'][1]}, regular season, FBS-vs-FBS, at each game's "
        "median closing number across CFBD's providers. One-sided exact binomial against 52.38% "
        "(110/210), pushes dropped; Holm at 5% across the six looks with m = 6 fixed.",
        "",
        "## The pre-registered criterion (verbatim)",
        "",
        f"> {row.criterion}",
        "",
        "## Result",
        "",
        f"- **Tested set:** {_rec_line(rec)}",
    ]
    if fam is None:
        out.append("- **Verdict:** NOT EVALUABLE (no graded bet in the tested set)")
    else:
        out.append(
            f"- **Holm-adjusted p with the other five unrun (p = 1):** {_p(fam['holm_p'])} -> {fam['verdict']}. "
            "A PASS here is final; otherwise the family table (`literature_look --holm`) decides "
            "once the other looks report."
        )
    out += [
        "",
        "## By season",
        "",
        "| season | record | rate | p | units |",
        "|---|---|---|---|---|",
    ]
    for s, r in res["by_season"].items():
        out.append(
            f"| {s} | {r['wins']}-{r['losses']}-{r['pushes']} | {_pct(r['rate'])} | {_p(r['p'])} | {r['units']:+.2f} |"
        )
    out += ["", "## Secondary (reported, never gated)", ""]
    for k, v in res["secondary"].items():
        if (
            isinstance(v, dict)
            and v
            and all(isinstance(x, dict) and "wins" in x for x in v.values())
        ):
            out.append(f"- **{k}:**")
            out += [f"  - {kk}: {_rec_line(vv)}" for kk, vv in v.items()]
        elif isinstance(v, dict) and "wins" in v:
            out.append(f"- **{k}:** {_rec_line(v)}")
        else:
            out.append(f"- **{k}:** {json.dumps(v)}")
    out += ["", "## Drops", "", f"- pooled: {json.dumps(res['drops'])}"]
    out += [f"- {s}: {json.dumps(d)}" for s, d in res["drops_by_season"].items()]
    out += ["", "## Provenance", ""]
    out.append(
        f"- CFBD calls left after the run: {calls_left if calls_left is not None else 'unknown'}"
    )
    out += [f"- providers, {k}: {json.dumps(v)}" for k, v in res["providers"].items()]
    if res["notes"]:
        out += ["", "## Notes", ""] + [f"- {n}" for n in res["notes"]]
    out += ["", "ONE dispatch per row: a second look goes in the row's `comparisons run`."]
    return "\n".join(out) + "\n"


def write_reports(out_dir: Path, row: Any, res: Dict[str, Any], calls_left: Optional[int]) -> Path:
    run_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"literature_{SLUG[res['row']]}_{run_at}"
    body = {k: v for k, v in res.items() if k != "rows"}
    body.update({"run_at": run_at, "criterion": row.criterion, "cfbd_calls_left": calls_left})
    stem.with_suffix(".json").write_text(json.dumps(body, indent=2, sort_keys=True, default=str))
    stem.with_suffix(".md").write_text(_md(row, res, run_at, calls_left))
    rows = res["rows"]
    if rows:
        with stem.with_suffix(".csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    return stem


def family_table(paths: Iterable[Path], out_dir: Path) -> Path:
    """The Holm family over finished looks' JSON reports (m = 6)."""
    pvals: Dict[str, float] = {}
    for p in paths:
        body = json.loads(Path(p).read_text())
        rid, pv = body["row"], body["record"]["p"]
        if rid in pvals:
            raise SystemExit(f"{rid} reported twice: one look per row")
        if pv is None:
            raise SystemExit(f"{rid} has no p-value (not evaluable); leave it out of the family")
        pvals[rid] = float(pv)
    fam = L.holm_family(pvals)
    lines = [
        f"# Literature looks — Holm family (m = {L.FAMILY_M}, {len(pvals)} of {L.FAMILY_M} run)",
        "",
        "| look | p | Holm-adjusted p | verdict |",
        "|---|---|---|---|",
    ] + [f"| {rid} | {_p(v['p'])} | {_p(v['holm_p'])} | {v['verdict']} |" for rid, v in fam.items()]
    text = "\n".join(lines) + "\n"
    print(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"literature_family_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.md"
    path.write_text(text)
    return path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--row", choices=sorted(L.LOOKS), help="the one look to run")
    ap.add_argument(
        "--holm", nargs="+", type=Path, metavar="JSON", help="finished looks' JSON reports"
    )
    ap.add_argument("--out", type=Path, default=Path("reports"))
    args = ap.parse_args(argv)
    if bool(args.row) == bool(args.holm):
        ap.error("give exactly one of --row or --holm")
    if args.holm:
        family_table(args.holm, args.out)
        return 0
    try:
        row = require_runnable_row(args.row)
    except HarnessRefusal as e:
        print(f"[literature] REFUSED: {e}", file=sys.stderr)
        return 2
    from beatvegas.sources.cfbd import CFBDClient

    client = CFBDClient()
    res = run_look(args.row, client, load_fbs_teams())
    stem = write_reports(args.out, row, res, getattr(client, "calls_remaining", None))
    rec = res["record"]
    print(f"[literature] {args.row}: {_rec_line(rec)} -> {stem}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
