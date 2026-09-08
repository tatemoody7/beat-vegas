#!/usr/bin/env python
"""Read-only look at the persisted model fits (model_artifacts).

    python scripts/model_artifacts.py list --engine residual [--limit 10]

One line per refit, newest first: when it was fitted, the slate it scored,
how many rows it trained on, the last game date it saw, the feature hash and
the scikit-learn version. A moved n_rows / max_game_date / feature_hash between
two rows in the same week is a mid-season change to the training history.

Read-only: no create_all / migrations / sequence resync (that is migrate.yml's
job, not a listing's). The blob column is never loaded.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from beatvegas.db.models import ModelArtifact
from beatvegas.db.store import get_engine, session_scope
from beatvegas.model.artifacts import newest_artifacts


def _fmt(row: ModelArtifact) -> str:
    fitted = row.fitted_at.strftime("%Y-%m-%d %H:%M") if row.fitted_at else "?"
    week = f"wk{row.week}" if row.week is not None else "wk?"
    return (
        f"{fitted}  {row.season} {week}  n_rows={row.n_rows}  "
        f"max_game_date={row.max_game_date}  feature_hash={row.feature_hash}  "
        f"sklearn={row.sklearn_version}"
    )


def list_artifacts(engine: str, limit: int) -> None:
    if not inspect(get_engine()).has_table(ModelArtifact.__tablename__):
        print("no artifacts yet (table not created; run migrate.yml)")
        return
    with session_scope() as s:
        rows = newest_artifacts(s, engine, limit)
        if not rows:
            print(f"no artifacts for engine {engine!r}")
            return
        print(f"{len(rows)} newest artifact(s) for engine {engine!r}:")
        for row in rows:
            print("  " + _fmt(row))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="the last N persisted fits for an engine")
    ls.add_argument("--engine", default="residual")
    ls.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    if args.cmd == "list":
        try:
            list_artifacts(args.engine, args.limit)
        except OperationalError as e:
            print(f"database unreachable: {e.orig or e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
