"""Open-Meteo weather API client."""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from tidewise.models import PressureTrend, WeatherData

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Unit conversion constants
HPA_TO_INHG = 0.02953
KMH_TO_MPH = 0.621371

# Pressure trend thresholds (inHg/hr)
RAPID_THRESHOLD = 0.06
CHANGE_THRESHOLD = 0.02


class WeatherAPIError(Exception):
    """Raised when the Open-Meteo API returns an error."""


async def fetch_weather(
    latitude: float,
    longitude: float,
    date: datetime,
    forecast_days: int = 2,
    client: httpx.AsyncClient | None = None,
) -> WeatherData:
    """Fetch weather data from Open-Meteo.

    Fetches 2 days by default to ensure backward data for pressure trend.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": ",".join([
            "temperature_2m",
            "pressure_msl",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "cloud_cover",
            "precipitation",
        ]),
        "forecast_days": forecast_days,
        "timezone": "auto",
    }

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        resp = await client.get(OPEN_METEO_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise WeatherAPIError(f"Open-Meteo API request failed: {e}") from e
    finally:
        if should_close:
            await client.aclose()

    if "error" in data:
        raise WeatherAPIError(f"Open-Meteo API error: {data.get('reason', data['error'])}")

    if "hourly" not in data:
        raise WeatherAPIError("Open-Meteo response missing 'hourly' key")

    return _parse_weather(data["hourly"], date)


def fetch_weather_sync(
    latitude: float,
    longitude: float,
    date: datetime,
) -> WeatherData:
    """Synchronous wrapper for fetch_weather."""
    return asyncio.run(fetch_weather(latitude, longitude, date))


def _parse_weather(hourly: dict, target: datetime) -> WeatherData:
    """Parse Open-Meteo hourly data, finding the closest hour to target."""
    times = hourly["time"]

    # Find closest hour index
    target_str = target.strftime("%Y-%m-%dT%H:00")
    try:
        idx = times.index(target_str)
    except ValueError:
        # Find nearest hour
        idx = _find_nearest_hour(times, target)

    # Current values with unit conversions
    temp_c = hourly["temperature_2m"][idx]
    temp_f = _celsius_to_fahrenheit(temp_c)

    pressure_hpa = hourly["pressure_msl"][idx]
    pressure_inhg = round(pressure_hpa * HPA_TO_INHG, 2)

    wind_kmh = hourly["wind_speed_10m"][idx]
    wind_mph = round(wind_kmh * KMH_TO_MPH, 1)

    gust_kmh = hourly["wind_gusts_10m"][idx]
    gust_mph = round(gust_kmh * KMH_TO_MPH, 1)

    wind_deg = hourly["wind_direction_10m"][idx]
    wind_cardinal = _degrees_to_cardinal(wind_deg)

    cloud_cover = hourly["cloud_cover"][idx]
    precipitation = hourly["precipitation"][idx]

    # Pressure trend: 3-hour lookback
    pressure_rate, pressure_trend = _calculate_pressure_trend(
        hourly["pressure_msl"], hourly["time"], idx
    )

    return WeatherData(
        temperature_f=round(temp_f, 1),
        pressure_inhg=pressure_inhg,
        pressure_trend=pressure_trend,
        pressure_rate=round(pressure_rate, 4),
        wind_speed_mph=wind_mph,
        wind_gust_mph=gust_mph,
        wind_direction=wind_cardinal,
        wind_direction_degrees=float(wind_deg),
        cloud_cover_pct=float(cloud_cover),
        precipitation_mm=float(precipitation),
        timestamp=datetime.strptime(times[idx], "%Y-%m-%dT%H:%M"),
    )


def _find_nearest_hour(times: list[str], target: datetime) -> int:
    """Find the index of the nearest hour to the target datetime."""
    target_ts = target.timestamp()
    min_diff = float("inf")
    best_idx = 0
    for i, t in enumerate(times):
        dt = datetime.strptime(t, "%Y-%m-%dT%H:%M")
        diff = abs(dt.timestamp() - target_ts)
        if diff < min_diff:
            min_diff = diff
            best_idx = i
    return best_idx


def _celsius_to_fahrenheit(c: float) -> float:
    return c * 9 / 5 + 32


def _calculate_pressure_trend(
    pressures: list[float], times: list[str], current_idx: int
) -> tuple[float, PressureTrend]:
    """Calculate pressure trend over a 3-hour window.

    Returns (rate_inhg_per_hr, trend_enum).
    """
    lookback_hours = 3
    start_idx = max(0, current_idx - lookback_hours)

    if start_idx == current_idx:
        return 0.0, PressureTrend.STEADY

    current_hpa = pressures[current_idx]
    past_hpa = pressures[start_idx]

    hours = current_idx - start_idx
    rate_hpa = (current_hpa - past_hpa) / hours
    rate_inhg = rate_hpa * HPA_TO_INHG

    if rate_inhg <= -RAPID_THRESHOLD:
        return rate_inhg, PressureTrend.RAPIDLY_FALLING
    elif rate_inhg <= -CHANGE_THRESHOLD:
        return rate_inhg, PressureTrend.FALLING
    elif rate_inhg >= RAPID_THRESHOLD:
        return rate_inhg, PressureTrend.RAPIDLY_RISING
    elif rate_inhg >= CHANGE_THRESHOLD:
        return rate_inhg, PressureTrend.RISING
    else:
        return rate_inhg, PressureTrend.STEADY


# 16-point compass rose
_CARDINAL_DIRECTIONS = [
    "N", "NNE", "NE", "ENE",
    "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW",
    "W", "WNW", "NW", "NNW",
]


def _degrees_to_cardinal(degrees: float) -> str:
    """Convert wind direction degrees to 16-point cardinal direction."""
    idx = round(degrees / 22.5) % 16
    return _CARDINAL_DIRECTIONS[idx]
