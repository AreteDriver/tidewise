"""Tests for Rich terminal display."""

from datetime import UTC, datetime
from io import StringIO

from rich.console import Console

from tidewise.config import ScoreWeights
from tidewise.display.terminal import (
    _moon_phase_display,
    _pressure_trend_arrow,
    _score_color,
    _tide_direction_display,
    render_best_windows,
    render_tide_forecast,
    render_today_summary,
)
from tidewise.models import (
    FishingScore,
    MoonPhase,
    PressureTrend,
    TideDirection,
)
from tidewise.scoring.engine import calculate_score


def _capture_console() -> tuple[Console, StringIO]:
    """Create a console that captures output."""
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=120), buf


class TestRenderTodaySummary:
    def test_renders_without_error(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        console, buf = _capture_console()
        render_today_summary(
            score, sample_tide_data, sample_weather_data, sample_solunar_data, console
        )
        output = buf.getvalue()
        assert "Fishing Score" in output
        assert "Tides" in output
        assert "Weather" in output
        assert "Solunar" in output
        assert "Suggestions" in output


class TestRenderTideForecast:
    def test_renders_predictions(self, sample_tide_data):
        console, buf = _capture_console()
        render_tide_forecast(sample_tide_data, console)
        output = buf.getvalue()
        assert "9439040" in output
        assert "HIGH" in output
        assert "LOW" in output


class TestRenderBestWindows:
    def test_renders_ranked(self, sample_tide_data, sample_weather_data, sample_solunar_data):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        console, buf = _capture_console()
        render_best_windows([(now, score)], console)
        output = buf.getvalue()
        assert "Best Fishing Windows" in output

    def test_empty_window_display(self, sample_tide_data, sample_weather_data, sample_solunar_data):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = FishingScore(
            composite=5.0,
            factors=[],
            best_window_start=now,
            best_window_end=None,
            best_window_reason="Test",
        )
        console, buf = _capture_console()
        render_best_windows([(now, score)], console)
        output = buf.getvalue()
        assert "From" in output


class TestHelpers:
    def test_score_color_green(self):
        assert _score_color(8.5) == "green"

    def test_score_color_yellow(self):
        assert _score_color(7.0) == "yellow"

    def test_score_color_orange(self):
        assert _score_color(5.0) == "dark_orange"

    def test_score_color_red(self):
        assert _score_color(3.0) == "red"

    def test_pressure_arrows(self):
        assert _pressure_trend_arrow(PressureTrend.RAPIDLY_FALLING) == "↓↓"
        assert _pressure_trend_arrow(PressureTrend.FALLING) == "↓"
        assert _pressure_trend_arrow(PressureTrend.STEADY) == "→"
        assert _pressure_trend_arrow(PressureTrend.RISING) == "↑"
        assert _pressure_trend_arrow(PressureTrend.RAPIDLY_RISING) == "↑↑"

    def test_tide_direction_display(self):
        assert "Incoming" in _tide_direction_display(TideDirection.INCOMING)
        assert "Outgoing" in _tide_direction_display(TideDirection.OUTGOING)
        assert "Slack" in _tide_direction_display(TideDirection.SLACK)

    def test_moon_phase_display(self):
        assert "New Moon" in _moon_phase_display(MoonPhase.NEW_MOON)
        assert "Full Moon" in _moon_phase_display(MoonPhase.FULL_MOON)
        assert "Waxing" in _moon_phase_display(MoonPhase.WAXING_CRESCENT)

    def test_suggestions_panel_empty(self):
        from tidewise.display.terminal import _build_suggestions_panel

        score = FishingScore(
            composite=5.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="",
            suggestions=[],
        )
        panel = _build_suggestions_panel(score)
        assert panel is not None
