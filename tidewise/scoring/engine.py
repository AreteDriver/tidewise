"""Composite scoring engine — combines individual factor scores."""

from __future__ import annotations

from datetime import datetime

from tidewise.config import ScoreWeights
from tidewise.models import (
    FactorScore,
    FishingScore,
    SolunarData,
    TideData,
    TideDirection,
    WaterTempData,
    WeatherData,
)
from tidewise.scoring.rules import (
    score_cloud_cover,
    score_precipitation,
    score_pressure,
    score_solunar,
    score_tide,
    score_water_temp,
    score_wind,
)
from tidewise.scoring.suggestions import generate_suggestions


def calculate_score(
    weights: ScoreWeights,
    tide: TideData,
    weather: WeatherData,
    solunar: SolunarData,
    now: datetime,
    water_temp: WaterTempData | None = None,
) -> FishingScore:
    """Calculate composite fishing score from all data sources.

    Weighted sum of individual factor scores, normalized to 1-10 scale.
    Water temp is optional — scoring degrades gracefully without it.
    """
    # Score each factor
    pressure_score, pressure_detail = score_pressure(weather.pressure_trend, weather.pressure_rate)
    tide_score, tide_detail = score_tide(tide, now, solunar)
    wind_score, wind_detail = score_wind(weather.wind_speed_mph, weather.wind_direction)
    cloud_score, cloud_detail = score_cloud_cover(weather.cloud_cover_pct)
    precip_score, precip_detail = score_precipitation(weather.precipitation_mm)
    solunar_score, solunar_detail = score_solunar(solunar, now)

    factors = [
        FactorScore("solunar", solunar_score, weights.solunar, solunar_detail),
        FactorScore("tide", tide_score, weights.tide, tide_detail),
        FactorScore("pressure", pressure_score, weights.pressure, pressure_detail),
        FactorScore("wind", wind_score, weights.wind, wind_detail),
        FactorScore("cloud", cloud_score, weights.cloud, cloud_detail),
        FactorScore("precipitation", precip_score, weights.precipitation, precip_detail),
    ]

    # Only include water_temp if data available AND weight > 0
    if water_temp is not None and weights.water_temp > 0:
        wt_score, wt_detail = score_water_temp(water_temp.temperature_f)
        factors.append(FactorScore("water_temp", wt_score, weights.water_temp, wt_detail))

    # Normalize weights so composite is always on 1-10 scale
    total_weight = sum(f.weight for f in factors)
    if total_weight > 0:
        composite = sum(f.score * f.weight for f in factors) / total_weight * 10
    else:
        composite = 1.0
    composite = round(max(1.0, min(10.0, composite)), 1)

    # Find best window
    best_start, best_end, best_reason = _find_best_window(tide, solunar, now)

    # Generate suggestions
    suggestions = generate_suggestions(factors, tide, weather, solunar, now)

    return FishingScore(
        composite=composite,
        factors=factors,
        best_window_start=best_start,
        best_window_end=best_end,
        best_window_reason=best_reason,
        suggestions=suggestions,
    )


def _find_best_window(
    tide: TideData,
    solunar: SolunarData,
    now: datetime,
) -> tuple[datetime | None, datetime | None, str]:
    """Find the best fishing window by overlapping solunar major with incoming tide.

    Returns (start, end, reason).
    """
    best_start = None
    best_end = None
    best_reason = "No optimal window identified"

    # Check for solunar major + incoming tide overlap
    for period in solunar.major_periods:
        if period.end < now:
            continue

        # Check if tide direction suggests incoming during this period
        # Simple heuristic: if the period is upcoming, suggest it
        if period.start >= now:
            best_start = period.start
            best_end = period.end
            if tide.current_direction == TideDirection.INCOMING:
                best_reason = (
                    f"Solunar major at {period.peak.strftime('%H:%M')} during incoming tide"
                )
            else:
                best_reason = f"Solunar major period at {period.peak.strftime('%H:%M')}"
            break
        elif period.start <= now <= period.end:
            # We're currently in a major period
            best_start = now
            best_end = period.end
            best_reason = f"Currently in solunar major (ends {period.end.strftime('%H:%M')})"
            break

    # Fallback: next incoming tide
    if best_start is None and tide.next_event:
        if tide.current_direction == TideDirection.INCOMING:
            best_start = now
            best_end = tide.next_event.time
            best_reason = f"Incoming tide until {tide.next_event.time.strftime('%H:%M')}"
        elif tide.current_direction == TideDirection.OUTGOING:
            best_start = tide.next_event.time
            best_reason = f"Wait for tide change at {tide.next_event.time.strftime('%H:%M')}"

    return best_start, best_end, best_reason
