"""Tests for configuration loading."""

import pytest

from tidewise.config import (
    LocationConfig,
    ScoreWeights,
    TideWiseConfig,
    load_config,
)


class TestDefaults:
    def test_default_config(self):
        cfg = TideWiseConfig()
        assert cfg.location.name == "Columbia River - Astoria"
        assert cfg.location.latitude == 46.1879
        assert cfg.location.timezone == "America/Los_Angeles"
        assert cfg.stations.tide == "9439040"
        assert cfg.preferences.units == "imperial"

    def test_default_weights_sum_to_one(self):
        w = ScoreWeights()
        total = w.solunar + w.tide + w.pressure + w.wind + w.cloud + w.precipitation
        assert abs(total - 1.0) < 1e-9

    def test_default_location(self):
        loc = LocationConfig()
        assert loc.longitude < 0  # West hemisphere


class TestLoadConfig:
    def test_load_defaults_when_no_file(self, tmp_path, monkeypatch):
        """Falls back to defaults when no config file exists."""
        monkeypatch.setattr(
            "tidewise.config._CONFIG_SEARCH_PATHS",
            [tmp_path / "nonexistent.yaml"],
        )
        cfg = load_config()
        assert cfg.location.name == "Columbia River - Astoria"

    def test_load_explicit_path(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            """
location:
  name: "Test Location"
  latitude: 45.0
  longitude: -122.0
  timezone: "America/New_York"

stations:
  tide: "1234567"

preferences:
  units: metric
  score_weights:
    solunar: 0.30
    tide: 0.30
    pressure: 0.15
    wind: 0.10
    cloud: 0.10
    precipitation: 0.05
"""
        )
        cfg = load_config(config_file)
        assert cfg.location.name == "Test Location"
        assert cfg.location.latitude == 45.0
        assert cfg.location.timezone == "America/New_York"
        assert cfg.stations.tide == "1234567"
        assert cfg.preferences.units == "metric"
        assert cfg.preferences.score_weights.solunar == 0.30

    def test_load_missing_explicit_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "missing.yaml")

    def test_load_partial_config(self, tmp_path):
        """Missing fields get defaults."""
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("location:\n  name: 'Partial'\n")
        cfg = load_config(config_file)
        assert cfg.location.name == "Partial"
        assert cfg.location.latitude == LocationConfig.latitude  # default
        assert cfg.stations.tide == "9439040"  # default

    def test_load_empty_yaml(self, tmp_path):
        """Empty YAML file returns all defaults."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")
        cfg = load_config(config_file)
        assert cfg.location.name == "Columbia River - Astoria"

    def test_search_path_order(self, tmp_path, monkeypatch):
        """First found config wins."""
        first = tmp_path / "first.yaml"
        second = tmp_path / "second.yaml"
        first.write_text("location:\n  name: 'First'\n")
        second.write_text("location:\n  name: 'Second'\n")
        monkeypatch.setattr("tidewise.config._CONFIG_SEARCH_PATHS", [first, second])
        cfg = load_config()
        assert cfg.location.name == "First"
