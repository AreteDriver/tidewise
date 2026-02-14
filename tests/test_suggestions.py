"""Tests for suggestion generator."""

from datetime import datetime, timezone

from tidewise.models import (
    FactorScore,
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
from tidewise.scoring.suggestions import generate_suggestions


def _make_weather(**kwargs):
    defaults = dict(
        temperature_f=52.0,
        pressure_inhg=29.82,
        pressure_trend=PressureTrend.STEADY,
        pressure_rate=0.0,
        wind_speed_mph=8.0,
        wind_gust_mph=14.0,
        wind_direction="SW",
        wind_direction_degrees=225.0,
        cloud_cover_pct=50.0,
        precipitation_mm=0.0,
        timestamp=datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return WeatherData(**defaults)


class TestSuggestions:
    def test_max_5_suggestions(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(
            pressure_trend=PressureTrend.RAPIDLY_FALLING,
            wind_speed_mph=25.0,
            cloud_cover_pct=5.0,
        )
        now = datetime(2026, 3, 15, 4, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert len(suggestions) <= 5

    def test_rapidly_falling_pressure(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(pressure_trend=PressureTrend.RAPIDLY_FALLING)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("dropping fast" in s for s in suggestions)

    def test_high_wind_advisory(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(wind_speed_mph=25.0, wind_gust_mph=35.0)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("sheltered" in s for s in suggestions)

    def test_bluebird_suggestion(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(cloud_cover_pct=5.0)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("bluebird" in s.lower() for s in suggestions)

    def test_full_moon_suggestion(self, sample_tide_data):
        base = datetime(2026, 3, 15, tzinfo=timezone.utc)
        solunar = SolunarData(
            major_periods=[],
            minor_periods=[],
            moon_phase=MoonPhase.FULL_MOON,
            moon_illumination=1.0,
            sunrise=None, sunset=None, moonrise=None, moonset=None,
        )
        weather = _make_weather()
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, solunar, now)
        assert any("full moon" in s.lower() for s in suggestions)

    def test_new_moon_suggestion(self, sample_tide_data):
        solunar = SolunarData(
            major_periods=[],
            minor_periods=[],
            moon_phase=MoonPhase.NEW_MOON,
            moon_illumination=0.0,
            sunrise=None, sunset=None, moonrise=None, moonset=None,
        )
        weather = _make_weather()
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, solunar, now)
        assert any("new moon" in s.lower() for s in suggestions)

    def test_east_wind_suggestion(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(wind_speed_mph=8.0, wind_direction="E")
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("east" in s.lower() for s in suggestions)

    def test_strong_wind_suggestion(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(wind_speed_mph=17.0, wind_gust_mph=22.0, wind_direction="NW")
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("strong wind" in s.lower() or "windward" in s.lower() for s in suggestions)

    def test_overcast_suggestion(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(cloud_cover_pct=90.0)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("overcast" in s.lower() for s in suggestions)

    def test_slack_tide_suggestion(self, sample_solunar_data):
        now = datetime(2026, 3, 15, 9, 30, tzinfo=timezone.utc)
        tide = TideData(
            predictions=[],
            current_direction=TideDirection.SLACK,
            next_event=TidePrediction(
                time=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
                height_ft=2.0,
                type=TideType.LOW,
            ),
            minutes_until_next=30,
            station_id="9439040",
        )
        weather = _make_weather()
        suggestions = generate_suggestions([], tide, weather, sample_solunar_data, now)
        assert any("slack" in s.lower() or "position" in s.lower() for s in suggestions)

    def test_in_major_period_incoming(self, sample_solunar_data):
        now = sample_solunar_data.major_periods[0].peak
        tide = TideData(
            predictions=[],
            current_direction=TideDirection.INCOMING,
            next_event=None,
            minutes_until_next=0,
            station_id="9439040",
        )
        weather = _make_weather()
        suggestions = generate_suggestions([], tide, weather, sample_solunar_data, now)
        assert any("fish now" in s.lower() for s in suggestions)

    def test_falling_pressure(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(pressure_trend=PressureTrend.FALLING)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("falling" in s.lower() for s in suggestions)

    def test_rapidly_rising_pressure(self, sample_tide_data, sample_solunar_data):
        weather = _make_weather(pressure_trend=PressureTrend.RAPIDLY_RISING)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=timezone.utc)
        suggestions = generate_suggestions([], sample_tide_data, weather, sample_solunar_data, now)
        assert any("lock jaw" in s.lower() or "slow" in s.lower() for s in suggestions)
