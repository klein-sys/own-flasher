"""
Unit tests — Config module.
"""

import json
import tempfile
from pathlib import Path

import pytest

from flashdock.config import Config


@pytest.fixture
def tmp_config(tmp_path: Path) -> Config:
    """Return a Config instance backed by a temp file."""
    return Config.load(tmp_path / "test_config.json")


class TestConfigDefaults:
    def test_first_run_true_by_default(self, tmp_config: Config):
        assert tmp_config.first_run is True

    def test_app_mode_defaults_to_simple(self, tmp_config: Config):
        assert tmp_config.get("app_mode") == "simple"

    def test_dry_run_false(self, tmp_config: Config):
        assert tmp_config.dry_run is False


class TestConfigSetGet:
    def test_set_and_get(self, tmp_config: Config):
        tmp_config.set("app_mode", "advanced")
        assert tmp_config.get("app_mode") == "advanced"

    def test_persists_to_disk(self, tmp_path: Path):
        path = tmp_path / "persist.json"
        cfg = Config.load(path)
        cfg.set("dry_run", True)
        # Reload from disk
        cfg2 = Config.load(path)
        assert cfg2.dry_run is True

    def test_reset_key(self, tmp_config: Config):
        tmp_config.set("min_battery_percent", 99)
        assert tmp_config.get("min_battery_percent") == 99
        tmp_config.reset("min_battery_percent")
        assert tmp_config.get("min_battery_percent") == 60

    def test_reset_all(self, tmp_config: Config):
        tmp_config.set("app_mode", "advanced")
        tmp_config.set("dry_run", True)
        tmp_config.reset_all()
        assert tmp_config.get("app_mode") == "simple"
        assert tmp_config.dry_run is False


class TestConfigCorrupted:
    def test_handles_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid json!!", encoding="utf-8")
        cfg = Config.load(bad)
        # Should fall back to defaults
        assert cfg.get("app_mode") == "simple"


class TestConfigProperties:
    def test_is_simple_mode(self, tmp_config: Config):
        assert tmp_config.is_simple_mode is True
        assert tmp_config.is_advanced_mode is False

    def test_tools_dir(self, tmp_config: Config):
        d = tmp_config.tools_dir
        assert isinstance(d, Path)

    def test_locked_serial_none(self, tmp_config: Config):
        assert tmp_config.locked_serial is None
