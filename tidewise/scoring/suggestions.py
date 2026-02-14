"""Natural language suggestion generator based on scored factors."""

from __future__ import annotations

from datetime import datetime

from tidewise.models import (
    FactorScore,
    MoonPhase,
    PressureTrend,
    SolunarData,
    SolunarPeriodType,
    TideData,
    TideDirection,
    WeatherData,
)


def generate_suggestions(
    factors: list[FactorScore],
    tide: TideData,
    weather: WeatherData,
    solunar: SolunarData,
    now: datetime,
) -> list[str]:
    """Generate up to 5 actionable fishing suggestions from current conditions."""
    suggestions: list[str] = []

    _add_tide_solunar_suggestion(suggestions, tide, solunar, now)
    _add_pressure_suggestion(suggestions, weather)
    _add_wind_suggestion(suggestions, weather)
    _add_cloud_suggestion(suggestions, weather)
    _add_moon_suggestion(suggestions, solunar)

    return suggestions[:5]


def _add_tide_solunar_suggestion(
    suggestions: list[str],
    tide: TideData,
    solunar: SolunarData,
    now: datetime,
) -> None:
    """Tide + solunar alignment suggestion."""
    # Check for upcoming alignment
    for period in solunar.major_periods:
        if period.start > now and tide.current_direction == TideDirection.INCOMING:
            suggestions.append(
                f"Incoming tide + solunar major at {period.peak.strftime('%H:%M')} "
                f"— best window today"
            )
            return
        elif period.start <= now <= period.end:
            if tide.current_direction == TideDirection.INCOMING:
                suggestions.append(
                    "You're in a solunar major during incoming tide — fish now!"
                )
            else:
                suggestions.append(
                    f"In solunar major period (until {period.end.strftime('%H:%M')}) "
                    f"— good activity expected"
                )
            return

    # Generic tide advice
    if tide.current_direction == TideDirection.INCOMING and tide.minutes_until_next > 120:
        suggestions.append("Incoming tide with strong current — fish the current seams")
    elif tide.current_direction == TideDirection.SLACK:
        if tide.next_event:
            suggestions.append(
                f"Slack tide — position for the change at "
                f"{tide.next_event.time.strftime('%H:%M')}"
            )


def _add_pressure_suggestion(suggestions: list[str], weather: WeatherData) -> None:
    """Pressure-based suggestion."""
    if weather.pressure_trend == PressureTrend.RAPIDLY_FALLING:
        suggestions.append(
            f"Pressure dropping fast ({weather.pressure_inhg:.2f} inHg) "
            f"— fish feeding aggressively, get out before the front"
        )
    elif weather.pressure_trend == PressureTrend.FALLING:
        suggestions.append(
            f"Falling pressure ({weather.pressure_inhg:.2f} inHg) "
            f"— good feeding activity expected"
        )
    elif weather.pressure_trend == PressureTrend.RAPIDLY_RISING:
        suggestions.append(
            "Pressure rising fast — fish may lock jaw, try slow presentations"
        )
    elif weather.pressure_trend == PressureTrend.STEADY and weather.pressure_rate >= 0:
        suggestions.append(
            "High stable pressure — fish deep structure, slow presentations"
        )


def _add_wind_suggestion(suggestions: list[str], weather: WeatherData) -> None:
    """Wind advisory suggestion."""
    if weather.wind_speed_mph >= 20:
        suggestions.append(
            f"Wind advisory: {weather.wind_speed_mph:.0f} mph from {weather.wind_direction} "
            f"(gusts {weather.wind_gust_mph:.0f} mph) — find sheltered water"
        )
    elif weather.wind_speed_mph >= 15:
        suggestions.append(
            f"Strong wind from {weather.wind_direction} ({weather.wind_speed_mph:.0f} mph) "
            f"— fish windward banks or sheltered spots"
        )
    elif weather.wind_direction.upper() in ("E", "NE", "ENE"):
        suggestions.append(
            f"Wind from the east ({weather.wind_direction}) — "
            f"fish bite least, try sheltered spots"
        )


def _add_cloud_suggestion(suggestions: list[str], weather: WeatherData) -> None:
    """Cloud cover tactical suggestion."""
    if weather.cloud_cover_pct < 10:
        suggestions.append(
            "Bluebird skies — fish deep structure, shaded banks, low-vis presentations"
        )
    elif weather.cloud_cover_pct >= 80:
        suggestions.append(
            "Overcast conditions — fish less cautious, standard presentations work well"
        )


def _add_moon_suggestion(suggestions: list[str], solunar: SolunarData) -> None:
    """Moon phase impact suggestion."""
    if solunar.moon_phase == MoonPhase.FULL_MOON:
        suggestions.append(
            f"Full moon ({solunar.moon_illumination*100:.0f}% illumination) "
            f"— stronger tidal movement, expect active night bite"
        )
    elif solunar.moon_phase == MoonPhase.NEW_MOON:
        suggestions.append(
            "New moon — strongest solunar influence, peak daytime feeding windows"
        )
