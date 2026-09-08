"""config.engine_name(): which 1H engine score_slate runs. Env BV_ENGINE wins,
else model.engine from the merged config, default "bv_line" (the incumbent
market-blind regressor). config.example.yaml IS the prod config (GHA has no
config.yaml), so it must ship with the incumbent selected."""

from pathlib import Path

import pytest
import yaml

from beatvegas import config

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_engines_tuple():
    assert config.ENGINES == ("bv_line", "residual")


def test_example_config_ships_the_incumbent():
    assert yaml.safe_load(EXAMPLE.read_text())["model"]["engine"] == "bv_line"


def test_default_is_bv_line(monkeypatch):
    monkeypatch.delenv("BV_ENGINE", raising=False)
    monkeypatch.setattr(config, "load_config", lambda: {})
    assert config.engine_name() == "bv_line"


def test_config_value_is_used(monkeypatch):
    monkeypatch.delenv("BV_ENGINE", raising=False)
    monkeypatch.setattr(config, "load_config", lambda: {"model": {"engine": "residual"}})
    assert config.engine_name() == "residual"


def test_env_overrides_config(monkeypatch):
    monkeypatch.setenv("BV_ENGINE", "residual")
    monkeypatch.setattr(config, "load_config", lambda: {"model": {"engine": "bv_line"}})
    assert config.engine_name() == "residual"


@pytest.mark.parametrize("bad", ["gbm", "", "BV_LINE"])
def test_unknown_engine_raises(monkeypatch, bad):
    monkeypatch.delenv("BV_ENGINE", raising=False)
    monkeypatch.setattr(config, "load_config", lambda: {"model": {"engine": bad}})
    with pytest.raises(ValueError):
        config.engine_name()


def test_unknown_env_engine_raises(monkeypatch):
    monkeypatch.setenv("BV_ENGINE", "nope")
    with pytest.raises(ValueError):
        config.engine_name()
