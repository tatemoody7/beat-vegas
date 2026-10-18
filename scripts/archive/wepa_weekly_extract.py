"""Derive `data/wepa_2025_weekly_z.csv` from the CFBD Patreon weekly files.

H-WEPA-F, ARM R (docs/HYPOTHESES.md). The 11 base 2025 weekly "Model Training
Data" files (weeks 5-15) are frozen Sunday snapshots of `/wepa/team/season`
"through week N-1". This script z-scores the 48 opponent-adjusted columns WITHIN
EACH FILE (over that file's games, per column) and writes only the z-scores
with `id, season, week, posted_at`; no raw value and no `spread` leaves the
gitignored research folder (Patreon terms: no redistribution; the spread is
market-aware and banned from every regressor). A sidecar `.meta.json` records
each source file's post id, sha256 and row count.

Idempotent: the same inputs give the same two files. The two mid-week "(Update)"
re-posts and the postseason files are skipped on purpose (the row says weeks
5-15, 561 games, the ids in `_2025_ids.txt`).

    PYTHONPATH=. python scripts/archive/wepa_weekly_extract.py [--src DIR] [--out data/wepa_2025_weekly_z.csv]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_GALLERY = Path("research/swarm/2026-10-05-cfbd-tier3/downloads/posts/gallery")


def _default_src() -> Path:
    """The gitignored gallery folder: here, or in the main checkout when this
    file runs from a worktree (the research folder is never copied there)."""
    here = ROOT / _GALLERY
    if here.exists():
        return here
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        main_root = (ROOT / common).resolve().parent
        if (main_root / _GALLERY).exists():
            return main_root / _GALLERY
    except (OSError, subprocess.CalledProcessError):
        pass
    return here


DEFAULT_SRC = _default_src()
DEFAULT_OUT = ROOT / "data" / "wepa_2025_weekly_z.csv"
SEASON = 2025

# The 48 adjusted columns, in the files' order: 12 metrics x {home, away} x {for, allowed}.
METRICS: Sequence[str] = (
    "epa",
    "rushing_epa",
    "passing_epa",
    "success",
    "standard_down_success",
    "passing_down_success",
    "line_yards",
    "second_level_yards",
    "open_field_yards",
    "explosiveness",
    "rush_explosiveness",
    "pass_explosiveness",
)
ADJUSTED_COLS: List[str] = [
    f"{side}_adjusted_{m}{suffix}"
    for m in METRICS
    for side in ("home", "away")
    for suffix in ("", "_allowed")
]
KEEP_COLS = ["id", "season", "week"]
_BASE_FILE = re.compile(
    r"^(?P<post>\d+)_Week (?P<week>\d+) Model Training Data \(Tier 3\+\)\s*_01\.csv$"
)


class ExtractRefusal(RuntimeError):
    pass


def base_weekly_files(src: Path) -> Dict[int, Path]:
    """{week: path} for the base 2025 weekly files only (no Update, no postseason)."""
    out: Dict[int, Path] = {}
    for p in sorted(src.glob("*.csv")):
        m = _BASE_FILE.match(p.name)
        if not m:
            continue
        head = pd.read_csv(p, nrows=1)
        if int(head["season"].iloc[0]) != SEASON:
            continue
        week = int(m.group("week"))
        if week in out:
            raise ExtractRefusal(f"two base files for week {week}: {out[week].name}, {p.name}")
        out[week] = p
    return out


def posted_at(csv_path: Path) -> Optional[str]:
    """The post's `published_at` from gallery-dl's sidecar JSON, if present."""
    for cand in (csv_path.with_suffix(csv_path.suffix + ".json"), csv_path.with_suffix(".json")):
        if cand.exists():
            try:
                return json.loads(cand.read_text()).get("published_at")
            except (OSError, ValueError):
                return None
    return None


def zscore_within(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Per column, (x - mean) / sd over the frame's rows (ddof 0). A constant
    column (sd 0) becomes 0.0 rather than NaN."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        x = pd.to_numeric(df[c], errors="coerce").astype(float)
        sd = float(x.std(ddof=0))
        out[f"z_{c}"] = 0.0 if sd == 0.0 else (x - float(x.mean())) / sd
    return out


def extract(files: Dict[int, Path], expected_ids: Optional[set] = None) -> pd.DataFrame:
    frames = []
    for week in sorted(files):
        df = pd.read_csv(files[week])
        missing = [c for c in KEEP_COLS + ADJUSTED_COLS if c not in df.columns]
        if missing:
            raise ExtractRefusal(f"{files[week].name}: missing columns {missing}")
        if (df["week"].astype(int) != week).any():
            raise ExtractRefusal(f"{files[week].name}: a row's week column is not {week}")
        if df["id"].duplicated().any():
            raise ExtractRefusal(f"{files[week].name}: duplicate game id")
        z = zscore_within(df, ADJUSTED_COLS)
        part = pd.concat([df[KEEP_COLS].astype(int), z], axis=1)
        part.insert(3, "posted_at", posted_at(files[week]))
        frames.append(part)
    out = pd.concat(frames, ignore_index=True)
    if out["id"].duplicated().any():
        dup = out.loc[out["id"].duplicated(), "id"].tolist()
        raise ExtractRefusal(f"game id(s) in more than one weekly file: {dup[:5]}")
    if expected_ids is not None and set(out["id"].tolist()) != set(expected_ids):
        only_files = sorted(set(out["id"]) - set(expected_ids))[:5]
        only_list = sorted(set(expected_ids) - set(out["id"]))[:5]
        raise ExtractRefusal(
            f"id set differs from the expected list: {len(out)} extracted vs "
            f"{len(expected_ids)} expected; only in files {only_files}, only in list {only_list}"
        )
    return out.sort_values(["week", "id"]).reset_index(drop=True)


def read_id_list(path: Path) -> set:
    return {int(t) for t in re.split(r"[,\s]+", path.read_text().strip()) if t}


def write_outputs(out: pd.DataFrame, files: Dict[int, Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False, float_format="%.6f")
    meta = {
        "row": "H-WEPA-F",
        "season": SEASON,
        "rows": int(len(out)),
        "weeks": sorted(int(w) for w in out["week"].unique()),
        "columns_zscored": ADJUSTED_COLS,
        "standardisation": "per column, within each weekly file, ddof 0; raw values not stored",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": [
            {
                "week": int(w),
                "file": files[w].name,
                "post_id": int(_BASE_FILE.match(files[w].name).group("post")),
                "sha256": hashlib.sha256(files[w].read_bytes()).hexdigest(),
                "rows": int((out["week"] == w).sum()),
                "posted_at": posted_at(files[w]),
            }
            for w in sorted(files)
        ],
    }
    meta_path = dest.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--src", type=Path, default=DEFAULT_SRC, help="gallery folder with the weekly CSVs"
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--ids",
        type=Path,
        default=None,
        help="id list to verify against (default: <src>/_2025_ids.txt when present)",
    )
    args = ap.parse_args(argv)
    files = base_weekly_files(args.src)
    if not files:
        print(f"no base {SEASON} weekly file under {args.src}", file=sys.stderr)
        return 2
    ids_path = args.ids or (args.src / "_2025_ids.txt")
    expected = read_id_list(ids_path) if ids_path.exists() else None
    try:
        out = extract(files, expected)
    except ExtractRefusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    meta_path = write_outputs(out, files, args.out)
    print(
        f"wrote {args.out} ({len(out)} rows, weeks {min(files)}-{max(files)}, "
        f"{len(ADJUSTED_COLS)} z columns) and {meta_path.name}"
        + ("" if expected is None else f"; id set == {ids_path.name} ({len(expected)})")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
