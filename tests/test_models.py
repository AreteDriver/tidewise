"""Tests for data models."""

from datetime import datetime, timezone

from tidewise.models import (
    FactorScore,
    FishingScore,
    MoonPhase,
    PressureTrend,
    SolunarData,
    SolunarPeriod,
    SolunarPeriodType,
    TideData,
    TideDirection,
    TidePrediction,
    TideType,
    WeatherData,
)


class TestEnums:
    def test_tide_type_values(self):
        assert TideType.HIGH == "high"
        assert TideType.LOW == "low"

    def test_tide_direction_values(self):
        assert TideDirection.INCOMING == "incoming"
        assert TideDirection.OUTGOING == "outgoing"
        assert TideDirection.SLACK == "slack"

    def test_pressure_trend_values(self):
        assert PressureTrend.RAPIDLY_FALLING == "rapidly_falling"
        assert PressureTrend.FALLING == "falling"
        assert PressureTrend.STEADY == "steady"
        assert PressureTrend.RISING == "rising"
        assert PressureTrend.RAPIDLY_RISING == "rapidly_rising"

    def test_moon_phase_values(self):
        assert len(MoonPhase) == 8
        assert MoonPhase.NEW_MOON == "new_moon"
        assert MoonPhase.FULL_MOON == "full_moon"

    def test_solunar_period_type_values(self):
        assert SolunarPeriodType.MAJOR == "major"
        assert SolunarPeriodType.MINOR == "minor"

    def test_enum_str_serialization(self):
        """StrEnum values serialize directly to strings."""
        assert str(TideType.HIGH) == "high"
        assert f"{PressureTrend.FALLING}" == "falling"


class TestTideModels:
    def test_tide_prediction_frozen(self):
        tp = TidePrediction(
            time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            height_ft=5.0,
            type=TideType.HIGH,
        )
        assert tp.height_ft == 5.0
        assert tp.type == TideType.HIGH

    def test_tide_data(self, sample_tide_data):
        assert len(sample_tide_data.predictions) == 4
        assert sample_tide_data.current_direction == TideDirection.INCOMING
        assert sample_tide_data.station_id == "9439040"
        assert sample_tide_data.minutes_until_next == 120


class TestWeatherModels:
    def test_weather_data(self, sample_weather_data):
        assert sample_weather_data.temperature_f == 52.0
        assert sample_weather_data.pressure_inhg == 29.82
        assert sample_weather_data.pressure_trend == PressureTrend.FALLING
        assert sample_weather_data.wind_direction == "SW"


class TestSolunarModels:
    def test_solunar_data(self, sample_solunar_data):
        assert len(sample_solunar_data.major_periods) == 2
        assert len(sample_solunar_data.minor_periods) == 2
        assert sample_solunar_data.moon_phase == MoonPhase.WAXING_GIBBOUS
        assert 0.0 <= sample_solunar_data.moon_illumination <= 1.0

    def test_solunar_period(self):
        now = datetime(2026, 1, 1, 6, 0, tzinfo=timezone.utc)
        period = SolunarPeriod(
            type=SolunarPeriodType.MAJOR,
            start=now.replace(hour=5),
            end=now.replace(hour=7),
            peak=now.replace(hour=6),
        )
        assert period.start < period.peak < period.end


class TestScoringModels:
    def test_factor_score(self):
        fs = FactorScore(name="pressure", score=0.9, weight=0.2, detail="Falling pressure")
        assert fs.name == "pressure"
        assert fs.score == 0.9

    def test_fishing_score(self):
        fs = FishingScore(
            composite=7.5,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="No data",
            suggestions=["Fish early"],
        )
        assert fs.composite == 7.5
        assert len(fs.suggestions) == 1

    def test_fishing_score_default_suggestions(self):
        fs = FishingScore(
            composite=5.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="",
        )
        assert fs.suggestions == []
