"""Individual scoring rules — pure functions returning (score, detail) tuples.

Each function returns a float 0.0-1.0 and a human-readable explanation.
"""

from __future__ import annotations

from datetime import datetime

from tidewise.models import (
    MoonPhase,
    PressureTrend,
    SolunarData,
    SolunarPeriodType,
    TideData,
    TideDirection,
)


def score_pressure(trend: PressureTrend, rate: float) -> tuple[float, str]:
    """Score barometric pressure trend for fishing quality."""
    if trend == PressureTrend.RAPIDLY_FALLING:
        return 1.0, f"Rapidly falling pressure ({rate:+.3f} inHg/hr) — fish feeding aggressively"
    elif trend == PressureTrend.FALLING:
        return 0.9, f"Falling pressure ({rate:+.3f} inHg/hr) — active feeding"
    elif trend == PressureTrend.STEADY:
        if rate < 0:
            return 0.7, "Steady low pressure — decent activity"
        else:
            return 0.4, "Steady high pressure — fish go deep, slow bite"
    elif trend == PressureTrend.RISING:
        return 0.6, f"Rising pressure ({rate:+.3f} inHg/hr) — improving"
    else:  # RAPIDLY_RISING
        return 0.3, f"Rapidly rising pressure ({rate:+.3f} inHg/hr) — lockjaw"


def score_tide(
    tide: TideData,
    now: datetime,
    solunar: SolunarData | None = None,
) -> tuple[float, str]:
    """Score current tide conditions for fishing quality."""
    direction = tide.current_direction
    minutes = tide.minutes_until_next
    next_event = tide.next_event

    base_score = 0.5
    detail = ""

    if direction == TideDirection.SLACK:
        if next_event and next_event.type.value == "high":
            base_score = 0.7
            detail = "Slack before incoming tide — positioning window"
        else:
            base_score = 0.3
            detail = "Dead slack — minimal water movement"
    elif direction == TideDirection.INCOMING:
        if minutes > 0 and next_event:
            # Hours since tide started incoming (estimate)
            if minutes > 240:  # > 4h until high = just started
                base_score = 0.9
                detail = "First hours of incoming tide — prime window"
            elif minutes > 120:
                base_score = 0.9
                detail = "Early incoming tide — strong current, active fish"
            else:
                base_score = 0.8
                detail = "Late incoming tide — still productive"
        else:
            base_score = 0.85
            detail = "Incoming tide — fish moving with current"
    elif direction == TideDirection.OUTGOING:
        if minutes > 240:
            base_score = 0.6
            detail = "Early outgoing tide — bait washing out"
        else:
            base_score = 0.5
            detail = "Outgoing tide — fish repositioning"

    # Solunar major period bonus
    if solunar:
        for period in solunar.major_periods:
            if period.start <= now <= period.end:
                base_score = min(1.0, base_score + 0.1)
                detail += " + solunar major alignment"
                break

    return round(base_score, 2), detail


def score_wind(speed_mph: float, direction: str) -> tuple[float, str]:
    """Score wind conditions for fishing quality."""
    # Base score from speed
    if speed_mph < 5:
        base_score = 0.8
        detail = f"Calm winds ({speed_mph:.0f} mph)"
    elif speed_mph < 10:
        base_score = 0.9
        detail = f"Light wind ({speed_mph:.0f} mph) — slight chop ideal"
    elif speed_mph < 15:
        base_score = 0.6
        detail = f"Moderate wind ({speed_mph:.0f} mph)"
    elif speed_mph < 20:
        base_score = 0.3
        detail = f"Strong wind ({speed_mph:.0f} mph) — tough conditions"
    else:
        base_score = 0.1
        detail = f"Gale force ({speed_mph:.0f} mph) — unsafe"

    # Direction bonus/penalty
    dir_upper = direction.upper()
    if dir_upper in ("S", "SW", "SSW"):
        base_score = min(1.0, base_score + 0.1)
        detail += f" from {direction} (favorable)"
    elif dir_upper in ("E", "NE", "ENE"):
        base_score = max(0.0, base_score - 0.1)
        detail += f" from {direction} (unfavorable)"
    else:
        detail += f" from {direction}"

    return round(base_score, 2), detail


def score_cloud_cover(cover_pct: float) -> tuple[float, str]:
    """Score cloud cover for fishing quality."""
    if cover_pct >= 80:
        return 0.9, f"Overcast ({cover_pct:.0f}%) — fish less cautious"
    elif cover_pct >= 40:
        return 0.7, f"Partly cloudy ({cover_pct:.0f}%)"
    elif cover_pct >= 10:
        return 0.5, f"Mostly clear ({cover_pct:.0f}%)"
    else:
        return 0.3, f"Bluebird skies ({cover_pct:.0f}%) — fish deep structure"


def score_precipitation(precip_mm: float) -> tuple[float, str]:
    """Score precipitation for fishing quality."""
    if precip_mm <= 0:
        return 0.7, "No precipitation"
    elif precip_mm <= 1:
        return 0.8, f"Light rain ({precip_mm:.1f}mm) — can trigger feeding"
    elif precip_mm <= 5:
        return 0.6, f"Moderate rain ({precip_mm:.1f}mm)"
    else:
        return 0.3, f"Heavy rain ({precip_mm:.1f}mm) — poor visibility"


def score_solunar(solunar: SolunarData, now: datetime) -> tuple[float, str]:
    """Score solunar period alignment for fishing quality."""
    # Check if we're in a major period
    for period in solunar.major_periods:
        if period.start <= now <= period.end:
            score = 1.0
            detail = f"In major solunar period (peak {period.peak.strftime('%H:%M')})"
            score += _moon_phase_bonus(solunar.moon_phase)
            return min(1.0, round(score, 2)), detail

    # Check if we're in a minor period
    for period in solunar.minor_periods:
        if period.start <= now <= period.end:
            score = 0.8
            detail = f"In minor solunar period (peak {period.peak.strftime('%H:%M')})"
            score += _moon_phase_bonus(solunar.moon_phase)
            return min(1.0, round(score, 2)), detail

    # Outside all periods — find next one
    next_period = None
    for period in sorted(
        solunar.major_periods + solunar.minor_periods, key=lambda p: p.start
    ):
        if period.start > now:
            next_period = period
            break

    score = 0.4 + _moon_phase_bonus(solunar.moon_phase)
    if next_period:
        kind = "major" if next_period.type == SolunarPeriodType.MAJOR else "minor"
        detail = f"Outside solunar periods — next {kind} at {next_period.start.strftime('%H:%M')}"
    else:
        detail = "Outside solunar periods"

    return min(1.0, round(score, 2)), detail


def _moon_phase_bonus(phase: MoonPhase) -> float:
    """Bonus score for favorable moon phases."""
    if phase in (MoonPhase.NEW_MOON, MoonPhase.FULL_MOON):
        return 0.15
    elif phase in (MoonPhase.FIRST_QUARTER, MoonPhase.LAST_QUARTER):
        return 0.05
    return 0.0
