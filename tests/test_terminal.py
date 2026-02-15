"""Tests for Rich terminal display."""

from datetime import UTC, datetime
from io import StringIO

from rich.console import Console

from tidewise.config import ScoreWeights
from tidewise.display.terminal import (
    _build_suggestions_panel,
    _build_tide_panel,
    _build_usgs_panel,
    _build_water_temp_panel,
    _build_weather_panel,
    _moon_phase_display,
    _pressure_trend_arrow,
    _score_color,
    _tide_direction_display,
    render_best_windows,
    render_score_history,
    render_tide_forecast,
    render_today_summary,
    render_week_forecast,
)
from tidewise.models import (
    FactorScore,
    FishingScore,
    MoonPhase,
    PressureTrend,
    TideDirection,
    USGSGaugeData,
    WaterTempData,
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

    def test_renders_with_water_temp(
        self,
        sample_tide_data,
        sample_weather_data,
        sample_solunar_data,
        sample_water_temp_data,
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        console, buf = _capture_console()
        render_today_summary(
            score,
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            console,
            water_temp=sample_water_temp_data,
        )
        output = buf.getvalue()
        assert "Water Temperature" in output

    def test_renders_with_usgs(
        self,
        sample_tide_data,
        sample_weather_data,
        sample_solunar_data,
        sample_usgs_data,
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        console, buf = _capture_console()
        render_today_summary(
            score,
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            console,
            usgs=sample_usgs_data,
        )
        output = buf.getvalue()
        assert "River Gauge" in output

    def test_renders_metric_units(
        self,
        sample_tide_data,
        sample_weather_data,
        sample_solunar_data,
        sample_water_temp_data,
        sample_usgs_data,
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        console, buf = _capture_console()
        render_today_summary(
            score,
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            console,
            water_temp=sample_water_temp_data,
            usgs=sample_usgs_data,
            units="metric",
        )
        output = buf.getvalue()
        assert "°C" in output
        assert "hPa" in output
        assert "km/h" in output

    def test_renders_with_console_none(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        """Default console creation when None passed."""
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = calculate_score(
            ScoreWeights(), sample_tide_data, sample_weather_data, sample_solunar_data, now
        )
        # Should not raise — exercises console=None branch
        render_today_summary(score, sample_tide_data, sample_weather_data, sample_solunar_data)


class TestRenderTideForecast:
    def test_renders_predictions(self, sample_tide_data):
        console, buf = _capture_console()
        render_tide_forecast(sample_tide_data, console)
        output = buf.getvalue()
        assert "9439040" in output
        assert "HIGH" in output
        assert "LOW" in output

    def test_renders_metric(self, sample_tide_data):
        console, buf = _capture_console()
        render_tide_forecast(sample_tide_data, console, units="metric")
        output = buf.getvalue()
        assert "Height (m)" in output

    def test_renders_with_console_none(self, sample_tide_data):
        render_tide_forecast(sample_tide_data)


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

    def test_empty_window_display(self):
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

    def test_renders_with_console_none(self):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score = FishingScore(
            composite=5.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="",
        )
        render_best_windows([(now, score)])


class TestRenderWeekForecast:
    def test_renders_table(self):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        scores = [
            (
                now,
                FishingScore(
                    composite=7.5,
                    factors=[FactorScore("solunar", 0.9, 0.25, "Good")],
                    best_window_start=now,
                    best_window_end=now.replace(hour=8),
                    best_window_reason="Solunar major",
                ),
            ),
            (
                now.replace(day=16),
                FishingScore(
                    composite=5.0,
                    factors=[FactorScore("tide", 0.5, 0.25, "OK")],
                    best_window_start=now.replace(day=16, hour=10),
                    best_window_end=None,
                    best_window_reason="Tide change",
                ),
            ),
            (
                now.replace(day=17),
                FishingScore(
                    composite=5.3,
                    factors=[],
                    best_window_start=None,
                    best_window_end=None,
                    best_window_reason="",
                ),
            ),
        ]
        console, buf = _capture_console()
        render_week_forecast(scores, console)
        output = buf.getvalue()
        assert "Weekly Fishing Forecast" in output
        assert "solunar" in output

    def test_trend_arrows(self):
        """Up, down, and steady trends."""
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        scores = [
            (now, FishingScore(5.0, [], None, None, "")),
            (now.replace(day=16), FishingScore(8.0, [], None, None, "")),  # up
            (now.replace(day=17), FishingScore(4.0, [], None, None, "")),  # down
            (now.replace(day=18), FishingScore(4.2, [], None, None, "")),  # steady
        ]
        console, buf = _capture_console()
        render_week_forecast(scores, console)
        output = buf.getvalue()
        assert "\u2191" in output  # up arrow
        assert "\u2193" in output  # down arrow
        assert "\u2192" in output  # right arrow

    def test_renders_with_console_none(self):
        render_week_forecast([])


class TestRenderScoreHistory:
    def test_renders_records(self):
        records = [
            {
                "timestamp": "2026-03-15T12:00:00+00:00",
                "composite": 8.0,
                "best_window_start": "2026-03-15T14:00:00+00:00",
                "best_window_end": "2026-03-15T16:00:00+00:00",
                "best_window_reason": "Solunar major",
            },
            {
                "timestamp": "2026-03-14T12:00:00+00:00",
                "composite": 5.0,
                "best_window_start": None,
                "best_window_end": None,
                "best_window_reason": "",
            },
        ]
        console, buf = _capture_console()
        render_score_history(records, console)
        output = buf.getvalue()
        assert "Score History" in output
        assert "records shown" in output
        assert "\u2191" in output  # 8.0 > 5.0 + 0.5

    def test_trend_down(self):
        records = [
            {"timestamp": "2026-03-15T12:00:00+00:00", "composite": 3.0},
            {"timestamp": "2026-03-14T12:00:00+00:00", "composite": 7.0},
        ]
        console, buf = _capture_console()
        render_score_history(records, console)
        output = buf.getvalue()
        assert "\u2193" in output

    def test_trend_steady(self):
        records = [
            {"timestamp": "2026-03-15T12:00:00+00:00", "composite": 5.0},
            {"timestamp": "2026-03-14T12:00:00+00:00", "composite": 5.2},
        ]
        console, buf = _capture_console()
        render_score_history(records, console)
        output = buf.getvalue()
        assert "\u2192" in output

    def test_single_record_no_trend(self):
        records = [
            {"timestamp": "2026-03-15T12:00:00+00:00", "composite": 5.0},
        ]
        console, buf = _capture_console()
        render_score_history(records, console)
        output = buf.getvalue()
        assert "records shown" in output

    def test_malformed_window_handled(self):
        """Bad window timestamps don't crash."""
        records = [
            {
                "timestamp": "2026-03-15T12:00:00+00:00",
                "composite": 5.0,
                "best_window_start": "not-a-date",
                "best_window_end": "also-bad",
                "best_window_reason": "test",
            },
        ]
        console, buf = _capture_console()
        render_score_history(records, console)
        output = buf.getvalue()
        assert "Score History" in output

    def test_renders_with_console_none(self):
        render_score_history([{"timestamp": "2026-03-15T12:00:00+00:00", "composite": 5.0}])


class TestMetricPanels:
    def test_tide_panel_metric(self, sample_tide_data):
        panel = _build_tide_panel(sample_tide_data, units="metric")
        assert panel is not None

    def test_tide_panel_imperial(self, sample_tide_data):
        panel = _build_tide_panel(sample_tide_data, units="imperial")
        assert panel is not None

    def test_weather_panel_metric(self, sample_weather_data):
        panel = _build_weather_panel(sample_weather_data, units="metric")
        assert panel is not None

    def test_weather_panel_imperial(self, sample_weather_data):
        panel = _build_weather_panel(sample_weather_data, units="imperial")
        assert panel is not None

    def test_water_temp_panel_metric(self, sample_water_temp_data):
        panel = _build_water_temp_panel(sample_water_temp_data, units="metric")
        assert panel is not None

    def test_water_temp_panel_cold(self):
        wt = WaterTempData(
            temperature_f=40.0, timestamp=datetime(2026, 3, 15, tzinfo=UTC), station_id="test"
        )
        panel = _build_water_temp_panel(wt)
        assert panel.border_style == "blue"

    def test_water_temp_panel_warm(self):
        wt = WaterTempData(
            temperature_f=55.0, timestamp=datetime(2026, 3, 15, tzinfo=UTC), station_id="test"
        )
        panel = _build_water_temp_panel(wt)
        assert panel.border_style == "green"

    def test_water_temp_panel_hot(self):
        wt = WaterTempData(
            temperature_f=70.0, timestamp=datetime(2026, 3, 15, tzinfo=UTC), station_id="test"
        )
        panel = _build_water_temp_panel(wt)
        assert panel.border_style == "red"


class TestUSGSPanel:
    def test_usgs_panel_imperial(self, sample_usgs_data):
        panel = _build_usgs_panel(sample_usgs_data, units="imperial")
        assert panel is not None

    def test_usgs_panel_metric(self, sample_usgs_data):
        panel = _build_usgs_panel(sample_usgs_data, units="metric")
        assert panel is not None

    def test_usgs_panel_discharge_only(self):
        usgs = USGSGaugeData(
            discharge_cfs=5000.0,
            gauge_height_ft=None,
            timestamp=datetime(2026, 3, 15, tzinfo=UTC),
            gauge_id="test",
        )
        panel = _build_usgs_panel(usgs)
        assert panel is not None

    def test_usgs_panel_gauge_height_only(self):
        usgs = USGSGaugeData(
            discharge_cfs=None,
            gauge_height_ft=4.2,
            timestamp=datetime(2026, 3, 15, tzinfo=UTC),
            gauge_id="test",
        )
        panel = _build_usgs_panel(usgs)
        assert panel is not None

    def test_usgs_panel_neither(self):
        usgs = USGSGaugeData(
            discharge_cfs=None,
            gauge_height_ft=None,
            timestamp=datetime(2026, 3, 15, tzinfo=UTC),
            gauge_id="test",
        )
        panel = _build_usgs_panel(usgs)
        assert panel is not None


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
