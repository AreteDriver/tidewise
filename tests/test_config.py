"""Tests for configuration loading."""

import pytest

from tidewise.config import (
    HistoryConfig,
    LocationConfig,
    NotificationConfig,
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


class TestNotificationConfig:
    def test_defaults(self):
        cfg = NotificationConfig()
        assert cfg.enabled is False
        assert cfg.method == "ntfy"
        assert cfg.ntfy_url == "https://ntfy.sh"
        assert cfg.ntfy_topic == "tidewise-fishing"
        assert cfg.alert_score == 8.0
        assert cfg.cooldown_minutes == 60

    def test_tidewise_config_has_notifications(self):
        cfg = TideWiseConfig()
        assert isinstance(cfg.notifications, NotificationConfig)
        assert cfg.notifications.enabled is False

    def test_parse_from_yaml(self, tmp_path):
        config_file = tmp_path / "notif.yaml"
        config_file.write_text(
            """
notifications:
  enabled: true
  method: both
  ntfy_url: "https://custom.ntfy.example.com"
  ntfy_topic: "my-fishing"
  alert_score: 7.5
  cooldown_minutes: 30
"""
        )
        cfg = load_config(config_file)
        assert cfg.notifications.enabled is True
        assert cfg.notifications.method == "both"
        assert cfg.notifications.ntfy_url == "https://custom.ntfy.example.com"
        assert cfg.notifications.ntfy_topic == "my-fishing"
        assert cfg.notifications.alert_score == 7.5
        assert cfg.notifications.cooldown_minutes == 30

    def test_partial_notification_config(self, tmp_path):
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("notifications:\n  enabled: true\n")
        cfg = load_config(config_file)
        assert cfg.notifications.enabled is True
        assert cfg.notifications.method == "ntfy"  # default
        assert cfg.notifications.alert_score == 8.0  # default

    def test_missing_notifications_section(self, tmp_path):
        config_file = tmp_path / "no_notif.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        cfg = load_config(config_file)
        assert cfg.notifications.enabled is False


class TestHistoryConfig:
    def test_defaults(self):
        cfg = HistoryConfig()
        assert cfg.enabled is True
        assert cfg.retention_days == 365

    def test_tidewise_config_has_history(self):
        cfg = TideWiseConfig()
        assert isinstance(cfg.history, HistoryConfig)
        assert cfg.history.enabled is True

    def test_parse_from_yaml(self, tmp_path):
        config_file = tmp_path / "hist.yaml"
        config_file.write_text(
            """
history:
  enabled: false
  retention_days: 90
"""
        )
        cfg = load_config(config_file)
        assert cfg.history.enabled is False
        assert cfg.history.retention_days == 90

    def test_partial_history_config(self, tmp_path):
        config_file = tmp_path / "partial.yaml"
        config_file.write_text("history:\n  retention_days: 180\n")
        cfg = load_config(config_file)
        assert cfg.history.enabled is True  # default
        assert cfg.history.retention_days == 180

    def test_missing_history_section(self, tmp_path):
        config_file = tmp_path / "no_hist.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        cfg = load_config(config_file)
        assert cfg.history.enabled is True
        assert cfg.history.retention_days == 365
