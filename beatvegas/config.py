"""Config loading. Reads config.yaml (falling back to config.example.yaml) and
allows the CFBD key to come from the CFBD_API_KEY environment variable."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=1)
def load_config() -> Dict[str, Any]:
    example = REPO_ROOT / "config.example.yaml"
    real = REPO_ROOT / "config.yaml"

    cfg: Dict[str, Any] = {}
    if example.exists():
        cfg = yaml.safe_load(example.read_text()) or {}
    if real.exists():
        cfg = _deep_merge(cfg, yaml.safe_load(real.read_text()) or {})

    # Environment overrides the file for secrets.
    env_key = os.environ.get("CFBD_API_KEY")
    if env_key:
        cfg.setdefault("cfbd", {})["api_key"] = env_key
    odds_env = os.environ.get("ODDS_API_KEY")
    if odds_env:
        cfg.setdefault("odds_api", {})["api_key"] = odds_env
    return cfg


def cfbd_api_key() -> str:
    key = (load_config().get("cfbd", {}) or {}).get("api_key", "")
    if not key:
        raise RuntimeError(
            "No CFBD API key. Get a free key at https://collegefootballdata.com/key, "
            "then set it in config.yaml (cfbd.api_key) or export CFBD_API_KEY."
        )
    return key


def odds_api_key() -> str:
    key = (load_config().get("odds_api", {}) or {}).get("api_key", "")
    if not key:
        raise RuntimeError(
            "No Odds API key. Get a free key at https://the-odds-api.com/ , then "
            "set it in config.yaml (odds_api.api_key) or export ODDS_API_KEY."
        )
    return key


def db_path() -> Path:
    # BEATVEGAS_DB env var overrides config (used for the demo/preview DB).
    rel = os.environ.get("BEATVEGAS_DB") or \
        (load_config().get("database", {}) or {}).get("path", "data/beatvegas.db")
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def database_url() -> str:
    """Full SQLAlchemy URL. Uses DATABASE_URL (e.g. Neon Postgres) when set,
    else a local SQLite file. Normalizes Postgres scheme to the psycopg driver."""
    env = os.environ.get("DATABASE_URL")
    if env:
        if env.startswith("postgresql://"):
            return env.replace("postgresql://", "postgresql+psycopg://", 1)
        if env.startswith("postgres://"):
            return env.replace("postgres://", "postgresql+psycopg://", 1)
        return env
    return f"sqlite:///{db_path()}"
