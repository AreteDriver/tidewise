"""Tests for Open-Meteo weather client."""

from datetime import datetime

import httpx
import pytest
import respx

from tidewise.models import PressureTrend
from tidewise.sources.weather import (
    OPEN_METEO_URL,
    WeatherAPIError,
    _calculate_pressure_trend,
    _celsius_to_fahrenheit,
    _degrees_to_cardinal,
    _find_nearest_hour,
    _parse_weather,
    fetch_weather,
)


HOURLY_DATA = {
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


class TestCelsiusToFahrenheit:
    def test_freezing(self):
        assert _celsius_to_fahrenheit(0) == 32

    def test_boiling(self):
        assert _celsius_to_fahrenheit(100) == 212

    def test_negative(self):
        assert _celsius_to_fahrenheit(-40) == -40


class TestDegreesToCardinal:
    @pytest.mark.parametrize(
        "degrees,expected",
        [
            (0, "N"),
            (22.5, "NNE"),
            (45, "NE"),
            (67.5, "ENE"),
            (90, "E"),
            (112.5, "ESE"),
            (135, "SE"),
            (157.5, "SSE"),
            (180, "S"),
            (202.5, "SSW"),
            (225, "SW"),
            (247.5, "WSW"),
            (270, "W"),
            (292.5, "WNW"),
            (315, "NW"),
            (337.5, "NNW"),
        ],
    )
    def test_all_16_directions(self, degrees, expected):
        assert _degrees_to_cardinal(degrees) == expected

    def test_360_wraps_to_north(self):
        assert _degrees_to_cardinal(360) == "N"

    def test_near_boundary(self):
        assert _degrees_to_cardinal(11) == "N"
        assert _degrees_to_cardinal(12) == "NNE"


class TestPressureTrend:
    def test_rapidly_falling(self):
        # Drop of 3 hPa over 3 hours = 1 hPa/hr = 0.02953 inHg/hr > 0.06? No.
        # Need bigger drop: 0.06 inHg/hr = 2.03 hPa/hr, so 6.1 hPa over 3 hours
        pressures = [1020.0, 1018.0, 1016.0, 1013.9]
        times = ["T00:00", "T01:00", "T02:00", "T03:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 3)
        assert trend == PressureTrend.RAPIDLY_FALLING
        assert rate < 0

    def test_falling(self):
        # ~0.03 inHg/hr = ~1.0 hPa/hr → 3 hPa over 3 hours
        pressures = [1013.0, 1012.0, 1011.0, 1010.0]
        times = ["T00:00", "T01:00", "T02:00", "T03:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 3)
        assert trend == PressureTrend.FALLING

    def test_steady(self):
        pressures = [1013.0, 1013.0, 1013.0, 1013.0]
        times = ["T00:00", "T01:00", "T02:00", "T03:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 3)
        assert trend == PressureTrend.STEADY

    def test_rising(self):
        pressures = [1010.0, 1011.0, 1012.0, 1013.0]
        times = ["T00:00", "T01:00", "T02:00", "T03:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 3)
        assert trend == PressureTrend.RISING

    def test_rapidly_rising(self):
        pressures = [1010.0, 1012.0, 1014.0, 1016.1]
        times = ["T00:00", "T01:00", "T02:00", "T03:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 3)
        assert trend == PressureTrend.RAPIDLY_RISING
        assert rate > 0

    def test_no_lookback_data(self):
        """First hour has no lookback — should be steady."""
        pressures = [1013.0]
        times = ["T00:00"]
        rate, trend = _calculate_pressure_trend(pressures, times, 0)
        assert trend == PressureTrend.STEADY


class TestParseWeather:
    def test_basic_parsing(self):
        target = datetime(2026, 3, 15, 6, 0)
        result = _parse_weather(HOURLY_DATA, target)
        assert result.temperature_f == pytest.approx(52.0, abs=0.1)
        assert result.pressure_inhg > 29.0
        assert result.wind_direction == "SW"
        assert result.cloud_cover_pct == 85.0

    def test_unit_conversions(self):
        target = datetime(2026, 3, 15, 6, 0)
        result = _parse_weather(HOURLY_DATA, target)
        # 12.9 km/h * 0.621371 = 8.0 mph
        assert result.wind_speed_mph == pytest.approx(8.0, abs=0.1)
        # 1009.2 hPa * 0.02953 = 29.80 inHg
        assert result.pressure_inhg == pytest.approx(29.80, abs=0.05)

    def test_nearest_hour_fallback(self):
        target = datetime(2026, 3, 15, 6, 30)  # no exact match
        result = _parse_weather(HOURLY_DATA, target)
        # Should match closest hour (06:00 or 07:00)
        assert result.temperature_f > 0


class TestFindNearestHour:
    def test_exact_match(self):
        times = ["2026-03-15T06:00", "2026-03-15T07:00"]
        assert _find_nearest_hour(times, datetime(2026, 3, 15, 6, 0)) == 0

    def test_nearest(self):
        times = ["2026-03-15T06:00", "2026-03-15T07:00"]
        assert _find_nearest_hour(times, datetime(2026, 3, 15, 6, 40)) == 1


class TestFetchWeather:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json={"hourly": HOURLY_DATA})
        )
        result = await fetch_weather(
            46.1879, -123.8313, datetime(2026, 3, 15, 6, 0)
        )
        assert result.temperature_f > 0
        assert result.pressure_inhg > 0
        assert result.wind_direction in (
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_response(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(
                200, json={"error": True, "reason": "Invalid params"}
            )
        )
        with pytest.raises(WeatherAPIError, match="Invalid params"):
            await fetch_weather(46.1879, -123.8313, datetime(2026, 3, 15, 6, 0))

    @respx.mock
    @pytest.mark.asyncio
    async def test_missing_hourly_key(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        with pytest.raises(WeatherAPIError, match="missing 'hourly'"):
            await fetch_weather(46.1879, -123.8313, datetime(2026, 3, 15, 6, 0))

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(500)
        )
        with pytest.raises(WeatherAPIError, match="request failed"):
            await fetch_weather(46.1879, -123.8313, datetime(2026, 3, 15, 6, 0))

    @respx.mock
    @pytest.mark.asyncio
    async def test_with_provided_client(self):
        respx.get(OPEN_METEO_URL).mock(
            return_value=httpx.Response(200, json={"hourly": HOURLY_DATA})
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_weather(
                46.1879, -123.8313, datetime(2026, 3, 15, 6, 0), client=client
            )
            assert result.temperature_f > 0
