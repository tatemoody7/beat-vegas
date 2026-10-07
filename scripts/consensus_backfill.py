#!/usr/bin/env python
"""Line value at the wager's exact terms for graded picks (docs/CONSENSUS.md).

    python scripts/consensus_backfill.py                 # report only (no writes)
    python scripts/consensus_backfill.py --write --missing-only   # grade.yml, nightly

Reads every GRADED row of manual_picks (real and paper) and challenger_picks,
computes the consensus engine's columns (`beatvegas.consensus.fields_for_pick`,
the same call `picks.grade_pick` makes) and either writes them (--write) or only
reports. The report is the protocol's input: per ledger, market and side, how
many rows have a reading, why the rest are excluded, and the mean and spread of
EV per unit against the consensus close and against Hard Rock's close.

Every row it reads is DEVELOPMENT evidence (docs/ROADMAP_2026.md: confirmatory
clocks start after the Statistical Protocol is registered). The report says
what the numbers look like; it decides nothing.

Writes reports/consensus_backfill_<UTC>.{md,json}. study.yml runs it as a
report and refuses --write; grade.yml runs it with --write --missing-only so a
row graded before this engine existed, or by a run that lacked the table, gets
its reading once.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from sqlalchemy.orm import load_only

from beatvegas.consensus import CONSENSUS_VERSION, SNAP_MARKET, HalfPointTable, fields_for_pick
from beatvegas.db.models import ChallengerPick, Game, ManualPick, OddsSnapshot
from beatvegas.db.store import session_scope, try_init_db

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 500
IN_BLOCK = 1000


def _ledger(pick) -> str:
    if isinstance(pick, ChallengerPick):
        return f"arm:{pick.arm}"
    return "paper" if pick.is_paper else "real"


def _summ(xs: List[float]) -> dict:
    if not xs:
        return {"n": 0}
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "sd": statistics.stdev(xs) if len(xs) > 1 else None,
        "median": statistics.median(xs),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--write", action="store_true", help="write the columns (grade.yml only)")
    ap.add_argument("--missing-only", action="store_true", help="only rows with no reading yet")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args(argv)
    if not try_init_db():
        return 1
    table = HalfPointTable.load()
    groups: Dict[tuple, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    written = 0
    with session_scope() as s:
        picks: list = []
        for model in (ManualPick, ChallengerPick):
            q = s.query(model).filter(model.graded.is_(True))
            if args.missing_only:
                q = q.filter(model.cons_version.is_(None))
            if not args.write and not args.missing_only:
                # A report reads only the decision fields, so it runs before the
                # new columns reach Neon (migrate.yml) as well as after.
                ident = model.is_paper if model is ManualPick else model.arm
                q = q.options(
                    load_only(
                        model.id,
                        model.game_id,
                        model.market,
                        model.side,
                        model.line,
                        model.price,
                        ident,
                    )
                )
            picks.extend(q.all())
        game_ids = sorted({p.game_id for p in picks if p.game_id is not None})
        games: Dict[int, Game] = {}
        snaps: Dict[tuple, list] = defaultdict(list)
        for i in range(0, len(game_ids), IN_BLOCK):
            block = game_ids[i : i + IN_BLOCK]
            for g in s.query(Game).filter(Game.id.in_(block)).all():
                games[g.id] = g
            for sn in (
                s.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id.in_(block))
                .filter(OddsSnapshot.market.in_(list(SNAP_MARKET.values())))
                .all()
            ):
                snaps[(sn.game_id, sn.market)].append(sn)
        for p in picks:
            game = games.get(p.game_id)
            market = SNAP_MARKET.get(p.market or "1H", "1H_total")
            kickoff = game.start_date if game is not None else None
            fields = fields_for_pick(snaps.get((p.game_id, market), []), kickoff, p, table)
            key = (_ledger(p), p.market or "1H", (p.side or "under").lower())
            g = groups[key]
            g["rows"].append(1)
            if fields["cons_excluded"]:
                g["excluded"].append(fields["cons_excluded"])
            if fields["ev_cons"] is not None:
                g["ev_cons"].append(fields["ev_cons"])
            if fields["ev_hr"] is not None:
                g["ev_hr"].append(fields["ev_hr"])
            if fields["cons_p_win"] is not None:
                g["p_win"].append(fields["cons_p_win"])
            if args.write:
                for k, v in fields.items():
                    setattr(p, k, v)
                written += 1
                if written % CHUNK == 0:
                    s.commit()
        if args.write:
            s.commit()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "version": CONSENSUS_VERSION,
        "table": table.version,
        "computed_at": stamp,
        "write": args.write,
        "missing_only": args.missing_only,
        "rows": sum(len(g["rows"]) for g in groups.values()),
        "written": written,
        "groups": {},
    }
    md = [
        f"# Consensus backfill ({CONSENSUS_VERSION}, table {table.version}, {stamp})",
        "",
        "Development evidence only (docs/ROADMAP_2026.md). EV is per unit staked, at each",
        "wager's own line and price, against the median de-vigged close of the counted books.",
        "",
        "| ledger | market | side | rows | with reading | excluded (why) | EV vs consensus: mean / sd / median | EV vs Hard Rock: mean / sd | mean P(win) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for key in sorted(groups):
        g = groups[key]
        ec, eh, pw = _summ(g["ev_cons"]), _summ(g["ev_hr"]), _summ(g["p_win"])
        why = ", ".join(f"{k} {v}" for k, v in Counter(g["excluded"]).most_common()) or "—"
        out["groups"]["|".join(key)] = {
            "rows": len(g["rows"]),
            "excluded": dict(Counter(g["excluded"])),
            "ev_cons": ec,
            "ev_hr": eh,
            "p_win": pw,
        }

        def f(d, k):
            v = d.get(k)
            return "—" if v is None else f"{v:+.3f}" if k != "sd" else f"{v:.3f}"

        mean_pw = "—" if pw["n"] == 0 else f"{pw['mean']:.3f}"
        md.append(
            f"| {key[0]} | {key[1]} | {key[2]} | {len(g['rows'])} | {ec['n']} | {why} | "
            f"{f(ec, 'mean')} / {f(ec, 'sd')} / {f(ec, 'median')} | {f(eh, 'mean')} / {f(eh, 'sd')} | "
            f"{mean_pw} |"
        )
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f"consensus_backfill_{stamp}.json").write_text(json.dumps(out, indent=1, default=str))
    (outdir / f"consensus_backfill_{stamp}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"rows {out['rows']}, written {written}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
