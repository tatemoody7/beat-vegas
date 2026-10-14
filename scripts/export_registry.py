"""Export the hypothesis registry for the site (2026-10-14, programme step 11).

`docs/HYPOTHESES.md` is the one source for every hypothesis's status; the site's
Research page shows the closed ones as a timeline. Vercel builds from `web/`, so
the page cannot read `../docs` at runtime: this script writes
`web/data/hypotheses.json` (prettier-ignored like its neighbours) and
`tests/test_hypotheses_registry.py` fails when the file and the registry differ,
so the export cannot drift.

    python scripts/export_registry.py          # rewrite web/data/hypotheses.json
    python scripts/export_registry.py --check  # exit 1 when the file is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beatvegas.registry import parse_registry  # noqa: E402

OUT = ROOT / "web" / "data" / "hypotheses.json"
KEEP = ("id", "question", "status", "family", "doc")


def export_rows() -> List[Dict[str, Any]]:
    rows = []
    for r in parse_registry():
        rows.append({k: getattr(r, k).strip() for k in KEEP})
    return rows


def render() -> str:
    return json.dumps(export_rows(), indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run scripts/export_registry.py")
            return 1
        print("up to date")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(export_rows())} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
