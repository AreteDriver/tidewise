"""Central data models — all dataclasses and enums live here to prevent circular imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# --- Enums ---


class TideType(StrEnum):
    HIGH = "high"
    LOW = "low"


class TideDirection(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    SLACK = "slack"


class PressureTrend(StrEnum):
    RAPIDLY_FALLING = "rapidly_falling"
    FALLING = "falling"
    STEADY = "steady"
    RISING = "rising"
    RAPIDLY_RISING = "rapidly_rising"


class MoonPhase(StrEnum):
    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


class SolunarPeriodType(StrEnum):
    MAJOR = "major"
    MINOR = "minor"


# --- Tide Models ---


@dataclass(frozen=True)
class TidePrediction:
    time: datetime
    height_ft: float
    type: TideType


@dataclass(frozen=True)
class TideData:
    predictions: list[TidePrediction]
    current_direction: TideDirection
    next_event: TidePrediction | None
    minutes_until_next: int
    station_id: str


# --- Weather Models ---


@dataclass(frozen=True)
class WeatherData:
    temperature_f: float
    pressure_inhg: float
    pressure_trend: PressureTrend
    pressure_rate: float  # inHg/hr
    wind_speed_mph: float
    wind_gust_mph: float
    wind_direction: str  # cardinal (N, NE, etc.)
    wind_direction_degrees: float
    cloud_cover_pct: float
    precipitation_mm: float
    timestamp: datetime


# --- Solunar Models ---


@dataclass(frozen=True)
class SolunarPeriod:
    type: SolunarPeriodType
    start: datetime
    end: datetime
    peak: datetime


@dataclass(frozen=True)
class SolunarData:
    major_periods: list[SolunarPeriod]
    minor_periods: list[SolunarPeriod]
    moon_phase: MoonPhase
    moon_illumination: float  # 0.0-1.0
    sunrise: datetime | None
    sunset: datetime | None
    moonrise: datetime | None
    moonset: datetime | None


# --- Scoring Models ---


@dataclass(frozen=True)
class FactorScore:
    name: str
    score: float  # 0.0-1.0
    weight: float
    detail: str


@dataclass(frozen=True)
class FishingScore:
    composite: float  # 1-10
    factors: list[FactorScore]
    best_window_start: datetime | None
    best_window_end: datetime | None
    best_window_reason: str
    suggestions: list[str] = field(default_factory=list)
