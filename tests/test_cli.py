"""Tests for CLI commands."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tidewise.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_sources(sample_tide_data, sample_weather_data, sample_solunar_data):
    """Patch _fetch_all_sources to return sample data."""
    with patch("tidewise.cli._fetch_all_sources") as mock:
        mock.return_value = (sample_tide_data, sample_weather_data, sample_solunar_data)
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


class TestMainGroup:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "TideWise" in result.output

    def test_subcommand_help(self, runner):
        result = runner.invoke(main, ["today", "--help"])
        assert result.exit_code == 0
