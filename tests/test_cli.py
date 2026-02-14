"""Tests for CLI commands."""

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from tidewise.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_sources(
    sample_tide_data, sample_weather_data, sample_solunar_data, sample_water_temp_data
):
    """Patch _fetch_all_sources to return sample data (4-tuple)."""
    with patch("tidewise.cli._fetch_all_sources") as mock:
        mock.return_value = (
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            sample_water_temp_data,
        )
        yield mock


class TestTodayCommand:
    def test_today_success(self, runner, mock_sources):
        result = runner.invoke(main, ["today"])
        assert result.exit_code == 0
        assert "Fishing Score" in result.output

    def test_today_with_config(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        result = runner.invoke(main, ["--config", str(config_file), "today"])
        assert result.exit_code == 0

    def test_today_fetch_error(self, runner):
        with patch("tidewise.cli._fetch_all_sources", side_effect=RuntimeError("API down")):
            result = runner.invoke(main, ["today"])
            assert result.exit_code == 1
            assert "Error" in result.output


class TestTidesCommand:
    def test_tides_success(self, runner, sample_tide_data):
        with patch("tidewise.sources.tides.fetch_tides_sync", return_value=sample_tide_data):
            result = runner.invoke(main, ["tides", "--days", "3"])
            assert result.exit_code == 0
            assert "9439040" in result.output

    def test_tides_error(self, runner):
        with patch(
            "tidewise.sources.tides.fetch_tides_sync",
            side_effect=RuntimeError("No connection"),
        ):
            result = runner.invoke(main, ["tides"])
            assert result.exit_code == 1


class TestScoreCommand:
    def test_score_default_date(self, runner, mock_sources):
        result = runner.invoke(main, ["score"])
        assert result.exit_code == 0
        assert "Fishing Score" in result.output

    def test_score_specific_date(self, runner, mock_sources):
        result = runner.invoke(main, ["score", "--date", "2026-03-15"])
        assert result.exit_code == 0

    def test_score_invalid_date(self, runner, mock_sources):
        result = runner.invoke(main, ["score", "--date", "not-a-date"])
        assert result.exit_code == 1
        assert "Invalid date" in result.output


class TestBestCommand:
    def test_best_windows(self, runner, mock_sources):
        result = runner.invoke(main, ["best", "--days", "3"])
        assert result.exit_code == 0
        assert "Best Fishing Windows" in result.output

    def test_best_all_fail(self, runner):
        with patch("tidewise.cli._fetch_all_sources", side_effect=RuntimeError("fail")):
            result = runner.invoke(main, ["best", "--days", "2"])
            assert "Could not fetch" in result.output or "Skipping" in result.output


class TestWeekCommand:
    def test_week_success(self, runner, mock_sources):
        result = runner.invoke(main, ["week"])
        assert result.exit_code == 0
        assert "Weekly Fishing Forecast" in result.output

    def test_week_custom_days(self, runner, mock_sources):
        result = runner.invoke(main, ["week", "--days", "3"])
        assert result.exit_code == 0
        assert "Weekly Fishing Forecast" in result.output

    def test_week_all_fail(self, runner):
        with patch("tidewise.cli._fetch_all_sources", side_effect=RuntimeError("fail")):
            result = runner.invoke(main, ["week", "--days", "2"])
            assert "Could not fetch" in result.output or "Skipping" in result.output

    def test_week_help(self, runner):
        result = runner.invoke(main, ["week", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output


class TestNotifyCommand:
    def test_notify_disabled(self, runner, mock_sources):
        """Notifications disabled in config — exits without sending."""
        result = runner.invoke(main, ["notify"])
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_notify_below_threshold(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "notif.yaml"
        config_file.write_text("notifications:\n  enabled: true\n  alert_score: 99.0\n")
        result = runner.invoke(main, ["--config", str(config_file), "notify"])
        assert result.exit_code == 0
        assert "No notification" in result.output

    def test_notify_force(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "notif.yaml"
        config_file.write_text("notifications:\n  enabled: true\n  method: none\n")
        with patch(
            "tidewise.notifications.send_notification",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = runner.invoke(main, ["--config", str(config_file), "notify", "--force"])
        assert result.exit_code == 0

    def test_notify_sends_successfully(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "notif.yaml"
        config_file.write_text("notifications:\n  enabled: true\n  alert_score: 1.0\n")
        with (
            patch(
                "tidewise.notifications.send_notification",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("tidewise.notifications.update_state"),
        ):
            result = runner.invoke(main, ["--config", str(config_file), "notify"])
        assert result.exit_code == 0
        assert "Notification sent" in result.output

    def test_notify_delivery_failure(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "notif.yaml"
        config_file.write_text("notifications:\n  enabled: true\n  alert_score: 1.0\n")
        with patch(
            "tidewise.notifications.send_notification",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = runner.invoke(main, ["--config", str(config_file), "notify"])
        assert result.exit_code == 0
        assert "failed" in result.output

    def test_notify_fetch_error(self, runner):
        with patch("tidewise.cli._fetch_all_sources", side_effect=RuntimeError("API")):
            result = runner.invoke(main, ["notify", "--force"])
            assert result.exit_code == 1
            assert "Error" in result.output

    def test_notify_help(self, runner):
        result = runner.invoke(main, ["notify", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output


class TestWatchCommand:
    def test_watch_disabled(self, runner, mock_sources):
        result = runner.invoke(main, ["watch"])
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_watch_help(self, runner):
        result = runner.invoke(main, ["watch", "--help"])
        assert result.exit_code == 0
        assert "--interval" in result.output


class TestHistoryCommand:
    def test_history_no_data(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        with patch("tidewise.history.get_recent_scores", return_value=[]):
            result = runner.invoke(main, ["--config", str(config_file), "history"])
        assert result.exit_code == 0
        assert "No history" in result.output

    def test_history_with_data(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        records = [
            {
                "timestamp": "2026-03-15T12:00:00+00:00",
                "location": "Test",
                "station_id": "9439040",
                "composite": 7.5,
                "best_window_start": "2026-03-15T14:00:00+00:00",
                "best_window_end": "2026-03-15T16:00:00+00:00",
                "best_window_reason": "Solunar major",
            },
        ]
        with (
            patch("tidewise.history.get_recent_scores", return_value=records),
            patch("tidewise.history.purge_old_records", return_value=0),
        ):
            result = runner.invoke(main, ["--config", str(config_file), "history"])
        assert result.exit_code == 0
        assert "Score History" in result.output
        assert "7.5" in result.output

    def test_history_export_csv(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        csv_path = tmp_path / "out.csv"
        records = [
            {
                "timestamp": "2026-03-15T12:00:00+00:00",
                "location": "Test",
                "station_id": "9439040",
                "composite": 7.5,
                "best_window_start": "2026-03-15T14:00:00+00:00",
                "best_window_end": "2026-03-15T16:00:00+00:00",
                "best_window_reason": "Solunar major",
            },
        ]
        with (
            patch("tidewise.history.get_recent_scores", return_value=records),
            patch("tidewise.history.purge_old_records", return_value=0),
        ):
            result = runner.invoke(
                main,
                ["--config", str(config_file), "history", "--export", str(csv_path)],
            )
        assert result.exit_code == 0
        assert "Exported 1 records" in result.output
        assert csv_path.exists()

    def test_history_export_no_data(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        csv_path = tmp_path / "out.csv"
        with patch("tidewise.history.get_recent_scores", return_value=[]):
            result = runner.invoke(
                main,
                ["--config", str(config_file), "history", "--export", str(csv_path)],
            )
        assert result.exit_code == 0
        assert "No history" in result.output

    def test_history_help(self, runner):
        result = runner.invoke(main, ["history", "--help"])
        assert result.exit_code == 0
        assert "--days" in result.output
        assert "--export" in result.output


class TestAutoLogging:
    def test_today_logs_score(self, runner, mock_sources):
        with patch("tidewise.history.log_score") as mock_log:
            result = runner.invoke(main, ["today"])
        assert result.exit_code == 0
        mock_log.assert_called_once()

    def test_score_logs_score(self, runner, mock_sources):
        with patch("tidewise.history.log_score") as mock_log:
            result = runner.invoke(main, ["score"])
        assert result.exit_code == 0
        mock_log.assert_called_once()

    def test_today_skips_log_when_disabled(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("history:\n  enabled: false\n")
        with patch("tidewise.history.log_score") as mock_log:
            result = runner.invoke(main, ["--config", str(config_file), "today"])
        assert result.exit_code == 0
        mock_log.assert_not_called()


class TestProfileOption:
    def test_profile_overrides_location_and_stations(self, runner, mock_sources, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text(
            """
profiles:
  newport:
    location:
      name: "Yaquina Bay - Newport"
      latitude: 44.6253
      longitude: -124.0535
      timezone: "America/Los_Angeles"
    stations:
      tide: "9435380"
      water_temp: "9435380"
"""
        )
        result = runner.invoke(
            main, ["--config", str(config_file), "--profile", "newport", "today"]
        )
        assert result.exit_code == 0
        # Verify the config was overridden by checking mock call args
        call_cfg = mock_sources.call_args[0][0]
        assert call_cfg.location.name == "Yaquina Bay - Newport"
        assert call_cfg.stations.tide == "9435380"

    def test_profile_not_found(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text("location:\n  name: 'Test'\n")
        result = runner.invoke(
            main, ["--config", str(config_file), "--profile", "nonexistent", "today"]
        )
        assert result.exit_code != 0
        assert "nonexistent" in result.output
        assert "not found" in result.output

    def test_profile_not_found_shows_available(self, runner, tmp_path):
        config_file = tmp_path / "cfg.yaml"
        config_file.write_text(
            """
profiles:
  astoria:
    location:
      name: "Astoria"
"""
        )
        result = runner.invoke(main, ["--config", str(config_file), "--profile", "bogus", "today"])
        assert result.exit_code != 0
        assert "astoria" in result.output


class TestMainGroup:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "TideWise" in result.output
        assert "--profile" in result.output

    def test_subcommand_help(self, runner):
        result = runner.invoke(main, ["today", "--help"])
        assert result.exit_code == 0
