#!/usr/bin/env python
"""Grade the factor credibility ledger against REAL 1H lines.

For every game with a real 1H line + result (results.line_kind == 'real'), bucket
each board factor into its green state and tally the 1H-under hit rate. Writes one
FactorLedger row per factor (Beta-binomial posterior + decay flag). Cumulative
across all seasons — never uses proxy lines, so it's immune to the proxy artifact.

    python scripts/grade_factor_ledger.py

Honest note: until real 1H lines are backfilled/captured (plan Phase 0), very few
games qualify, so most factors show tiny n / wide credible intervals — which is
exactly the point: the card shows n loudly so you don't over-read a handful.
"""

from __future__ import annotations

from datetime import datetime

from beatvegas.db.models import FactorLedger, Result
from beatvegas.db.store import init_db, session_scope
from beatvegas.etl.features import build_feature_frame
from beatvegas.factors.ledger import grade_ledger


def main() -> None:
    init_db()
    df = build_feature_frame()

    with session_scope() as s:
        real = s.query(Result).filter(Result.line_kind == "real").all()
        outcomes = {int(r.game_id): (1 if r.under_hit else 0) for r in real}

        if not outcomes:
            print("[ledger] no real-line results yet — nothing to grade (see plan Phase 0).")
            return

        graded = df[df["id"].isin(outcomes.keys())].copy()
        graded["order"] = graded["season"] * 100 + graded["week"]
        rows = grade_ledger(graded, outcomes)

        s.query(FactorLedger).delete()
        now = datetime.utcnow()
        for r in rows:
            s.add(FactorLedger(created_at=now, **r))

    promoted = [r["factor"] for r in rows if r["tier"] == 1]
    cooling = [r["factor"] for r in rows if r["drift_flag"]]
    print(
        f"[ledger] graded {len(outcomes)} real-line games → {len(rows)} factors. "
        f"promoted={promoted or '—'} cooling={cooling or '—'}"
    )


if __name__ == "__main__":
    main()
