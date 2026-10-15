"""Freeze data/shortlist_reference.json for the research shortlist (H-1H-SHORTLIST, one-off).

Reads the H-1H-FACTORS screen's local outputs (`research/1h-factors-2026-10/frame.json` and
`screen.json`, gitignored) and writes, for each descriptive stat the shortlist shows, the sorted
2023-26 frame values (its percentiles are read against them, exactly as the prototype did) and the
screen verdict ("null" unless a factor passed Level 1). Run by hand when the screen is re-run;
`beatvegas/shortlist.py` only reads the committed file.

    python scripts/build_shortlist_reference.py [--research research/1h-factors-2026-10]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from beatvegas.shortlist import CONTEXT, REFERENCE_PATH

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--research", default=str(ROOT / "research" / "1h-factors-2026-10"))
    args = ap.parse_args()
    d = Path(args.research)
    frame = json.loads((d / "frame.json").read_text())
    screen = json.loads((d / "screen.json").read_text())
    keys = [k for k, _, _ in CONTEXT]
    values = {k: sorted(r[k] for r in frame if r.get(k) is not None) for k in keys}
    verdicts = {}
    for x in screen:
        l2 = (x.get("l2") or {}).get("level2")
        verdicts[x["factor"]] = (
            "candidate" if x.get("level1") and l2 else "preliminary" if x.get("level1") else "null"
        )
    out = {
        "source": "H-1H-FACTORS screen, research/1h-factors-2026-10 (frame.json, screen.json)",
        "frame_rows": len(frame),
        "factors_screened": len(screen),
        "values": values,
        "verdicts": {k: verdicts.get(k, "not screened") for k in keys + ["wx_wind"]},
    }
    REFERENCE_PATH.write_text(json.dumps(out, sort_keys=True) + "\n")
    print(f"wrote {REFERENCE_PATH} ({len(frame)} frame rows, {len(screen)} factors screened)")
    for k in keys:
        print(f"  {k}: {len(values[k])} values, verdict {out['verdicts'][k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
