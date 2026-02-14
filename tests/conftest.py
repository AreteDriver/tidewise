"""Shared test fixtures and mock API responses."""

from datetime import UTC, datetime

import pytest

from tidewise.config import (
    LocationConfig,
    PreferencesConfig,
    ScoreWeights,
    StationConfig,
    TideWiseConfig,
)
from tidewise.models import (
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


@pytest.fixture
def config() -> TideWiseConfig:
    return TideWiseConfig(
        location=LocationConfig(
            name="Columbia River - Astoria",
            latitude=46.1879,
            longitude=-123.8313,
            timezone="America/Los_Angeles",
        ),
        stations=StationConfig(tide="9439040"),
        preferences=PreferencesConfig(score_weights=ScoreWeights()),
    )


@pytest.fixture
def sample_tide_data() -> TideData:
    base = datetime(2026, 3, 15, tzinfo=UTC)
    return TideData(
        predictions=[
            TidePrediction(
                time=base.replace(hour=3, minute=22),
                height_ft=1.2,
                type=TideType.LOW,
            ),
            TidePrediction(
                time=base.replace(hour=9, minute=45),
                height_ft=8.1,
                type=TideType.HIGH,
            ),
            TidePrediction(
                time=base.replace(hour=15, minute=58),
                height_ft=2.3,
                type=TideType.LOW,
            ),
            TidePrediction(
                time=base.replace(hour=22, minute=10),
                height_ft=7.5,
                type=TideType.HIGH,
            ),
        ],
        current_direction=TideDirection.INCOMING,
        next_event=TidePrediction(
            time=base.replace(hour=9, minute=45),
            height_ft=8.1,
            type=TideType.HIGH,
        ),
        minutes_until_next=120,
        station_id="9439040",
    )


@pytest.fixture
def sample_weather_data() -> WeatherData:
    return WeatherData(
        temperature_f=52.0,
        pressure_inhg=29.82,
        pressure_trend=PressureTrend.FALLING,
        pressure_rate=-0.04,
        wind_speed_mph=8.0,
        wind_gust_mph=14.0,
        wind_direction="SW",
        wind_direction_degrees=225.0,
        cloud_cover_pct=85.0,
        precipitation_mm=0.0,
        timestamp=datetime(2026, 3, 15, 6, 0, tzinfo=UTC),
    )


@pytest.fixture
def sample_solunar_data() -> SolunarData:
    base = datetime(2026, 3, 15, tzinfo=UTC)
    return SolunarData(
        major_periods=[
            SolunarPeriod(
                type=SolunarPeriodType.MAJOR,
                start=base.replace(hour=5, minute=15),
                end=base.replace(hour=7, minute=15),
                peak=base.replace(hour=6, minute=15),
            ),
            SolunarPeriod(
                type=SolunarPeriodType.MAJOR,
                start=base.replace(hour=17, minute=45),
                end=base.replace(hour=19, minute=45),
                peak=base.replace(hour=18, minute=45),
            ),
        ],
        minor_periods=[
            SolunarPeriod(
                type=SolunarPeriodType.MINOR,
                start=base.replace(hour=11, minute=30),
                end=base.replace(hour=12, minute=30),
                peak=base.replace(hour=12, minute=0),
            ),
            SolunarPeriod(
                type=SolunarPeriodType.MINOR,
                start=base.replace(hour=23, minute=50),
                end=base.replace(hour=0, minute=50),
                peak=base.replace(hour=0, minute=20),
            ),
        ],
        moon_phase=MoonPhase.WAXING_GIBBOUS,
        moon_illumination=0.72,
        sunrise=base.replace(hour=14, minute=20),
        sunset=base.replace(hour=1, minute=30),
        moonrise=base.replace(hour=17, minute=0),
        moonset=base.replace(hour=6, minute=0),
    )


# --- Mock API Responses ---

NOAA_TIDE_RESPONSE = {
    "predictions": [
        {"t": "2026-03-15 03:22", "v": "1.200", "type": "L"},
        {"t": "2026-03-15 09:45", "v": "8.100", "type": "H"},
        {"t": "2026-03-15 15:58", "v": "2.300", "type": "L"},
        {"t": "2026-03-15 22:10", "v": "7.500", "type": "H"},
    ]
}

OPEN_METEO_RESPONSE = {
    "hourly": {
        "time": [
            "2026-03-15T03:00",
            "2026-03-15T04:00",
            "2026-03-15T05:00",
            "2026-03-15T06:00",
            "2026-03-15T07:00",
            "2026-03-15T08:00",
        ],
        "temperature_2m": [10.5, 10.2, 10.0, 11.1, 11.5, 12.0],
        "pressure_msl": [1010.0, 1009.8, 1009.5, 1009.2, 1009.0, 1008.7],
        "wind_speed_10m": [12.0, 13.0, 14.0, 12.9, 11.5, 10.0],
        "wind_direction_10m": [225, 230, 220, 225, 215, 210],
        "wind_gusts_10m": [20.0, 22.0, 24.0, 22.5, 20.0, 18.0],
        "cloud_cover": [80, 85, 90, 85, 80, 75],
        "precipitation": [0.0, 0.0, 0.0, 0.1, 0.0, 0.0],
    }
}
