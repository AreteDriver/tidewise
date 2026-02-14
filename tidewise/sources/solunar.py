"""Solunar engine — moon/sun calculations via Skyfield ephemeris."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from skyfield import almanac
from skyfield.api import Loader, Topos, wgs84

from tidewise.models import MoonPhase, SolunarData, SolunarPeriod, SolunarPeriodType

_DATA_DIR = Path.home() / ".local" / "share" / "tidewise"
_loader: Loader | None = None
_ephemeris = None
_ts = None


def _get_loader() -> Loader:
    global _loader
    if _loader is None:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _loader = Loader(str(_DATA_DIR))
    return _loader


def _get_ephemeris():
    global _ephemeris, _ts
    if _ephemeris is None:
        loader = _get_loader()
        _ephemeris = loader("de421.bsp")
        _ts = loader.timescale()
    return _ephemeris, _ts


def get_solunar_data(
    latitude: float,
    longitude: float,
    date: datetime,
    tz_name: str = "America/Los_Angeles",
) -> SolunarData:
    """Compute solunar data for a location and date.

    All internal math in UTC. Results converted to local timezone.
    """
    eph, ts = _get_ephemeris()
    tz = ZoneInfo(tz_name)

    # Build time window: local midnight to local midnight+1 day
    local_midnight = datetime(date.year, date.month, date.day, tzinfo=tz)
    utc_start = local_midnight.astimezone(UTC)
    utc_end = utc_start + timedelta(days=1)

    t0 = ts.from_datetime(utc_start)
    t1 = ts.from_datetime(utc_end)

    topos = Topos(latitude, longitude)  # needed for meridian_transits
    observer = eph["Earth"] + wgs84.latlon(latitude, longitude)  # for rise/set

    moon_phase = _compute_moon_phase(eph, ts, utc_start)
    moon_illumination = _compute_moon_illumination(eph, ts, utc_start)

    major_periods = _compute_major_periods(eph, ts, topos, t0, t1, tz)
    minor_periods = _compute_minor_periods(eph, ts, observer, t0, t1, tz)

    sunrise, sunset = _compute_sun_rise_set(eph, ts, observer, t0, t1, tz)
    moonrise, moonset = _compute_moon_rise_set_times(eph, ts, observer, t0, t1, tz)

    return SolunarData(
        major_periods=major_periods,
        minor_periods=minor_periods,
        moon_phase=moon_phase,
        moon_illumination=moon_illumination,
        sunrise=sunrise,
        sunset=sunset,
        moonrise=moonrise,
        moonset=moonset,
    )


def _compute_moon_phase(eph, ts, utc_dt: datetime) -> MoonPhase:
    """Compute moon phase from phase angle (0-360 degrees)."""
    t = ts.from_datetime(utc_dt)
    angle = almanac.moon_phase(eph, t).degrees
    return _phase_angle_to_name(angle)


def _compute_moon_illumination(eph, ts, utc_dt: datetime) -> float:
    """Compute moon illumination fraction (0.0-1.0)."""
    t = ts.from_datetime(utc_dt)
    angle_rad = math.radians(almanac.moon_phase(eph, t).degrees)
    return round((1 - math.cos(angle_rad)) / 2, 4)


def _phase_angle_to_name(angle: float) -> MoonPhase:
    """Map phase angle (0-360) to one of 8 moon phase names.

    Each phase spans 45 degrees centered on its canonical angle.
    """
    # Normalize to 0-360
    angle = angle % 360

    if angle < 22.5 or angle >= 337.5:
        return MoonPhase.NEW_MOON
    elif angle < 67.5:
        return MoonPhase.WAXING_CRESCENT
    elif angle < 112.5:
        return MoonPhase.FIRST_QUARTER
    elif angle < 157.5:
        return MoonPhase.WAXING_GIBBOUS
    elif angle < 202.5:
        return MoonPhase.FULL_MOON
    elif angle < 247.5:
        return MoonPhase.WANING_GIBBOUS
    elif angle < 292.5:
        return MoonPhase.LAST_QUARTER
    else:
        return MoonPhase.WANING_CRESCENT


def _compute_major_periods(eph, ts, location, t0, t1, tz: ZoneInfo) -> list[SolunarPeriod]:
    """Major solunar periods: ~2h centered on moon transit (overhead) and anti-transit (underfoot).

    Uses meridian_transits to find when the moon crosses the observer's meridian.
    """
    periods = []
    moon = eph["Moon"]
    f = almanac.meridian_transits(eph, moon, location)
    times, events = almanac.find_discrete(t0, t1, f)

    for t, _event in zip(times, events, strict=False):
        # event 0 = anti-transit (underfoot), 1 = transit (overhead)
        peak_utc = t.utc_datetime().replace(tzinfo=UTC)
        peak_local = peak_utc.astimezone(tz)
        start = peak_local - timedelta(hours=1)
        end = peak_local + timedelta(hours=1)
        periods.append(
            SolunarPeriod(
                type=SolunarPeriodType.MAJOR,
                start=start,
                end=end,
                peak=peak_local,
            )
        )

    return periods


def _compute_minor_periods(eph, ts, location, t0, t1, tz: ZoneInfo) -> list[SolunarPeriod]:
    """Minor solunar periods: ~1h centered on moonrise and moonset."""
    periods = []
    moon = eph["Moon"]

    # Moonrise
    rise_times, rise_is_real = almanac.find_risings(location, moon, t0, t1)
    for t, is_real in zip(rise_times, rise_is_real, strict=False):
        if not is_real:
            continue
        peak_utc = t.utc_datetime().replace(tzinfo=UTC)
        peak_local = peak_utc.astimezone(tz)
        periods.append(
            SolunarPeriod(
                type=SolunarPeriodType.MINOR,
                start=peak_local - timedelta(minutes=30),
                end=peak_local + timedelta(minutes=30),
                peak=peak_local,
            )
        )

    # Moonset
    set_times, set_is_real = almanac.find_settings(location, moon, t0, t1)
    for t, is_real in zip(set_times, set_is_real, strict=False):
        if not is_real:
            continue
        peak_utc = t.utc_datetime().replace(tzinfo=UTC)
        peak_local = peak_utc.astimezone(tz)
        periods.append(
            SolunarPeriod(
                type=SolunarPeriodType.MINOR,
                start=peak_local - timedelta(minutes=30),
                end=peak_local + timedelta(minutes=30),
                peak=peak_local,
            )
        )

    return sorted(periods, key=lambda p: p.start)


def _compute_sun_rise_set(
    eph, ts, location, t0, t1, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Compute sunrise and sunset times."""
    sun = eph["Sun"]
    sunrise = sunset = None

    rise_times, rise_is_real = almanac.find_risings(location, sun, t0, t1)
    for t, is_real in zip(rise_times, rise_is_real, strict=False):
        if is_real:
            sunrise = t.utc_datetime().replace(tzinfo=UTC).astimezone(tz)
            break

    set_times, set_is_real = almanac.find_settings(location, sun, t0, t1)
    for t, is_real in zip(set_times, set_is_real, strict=False):
        if is_real:
            sunset = t.utc_datetime().replace(tzinfo=UTC).astimezone(tz)
            break

    return sunrise, sunset


def _compute_moon_rise_set_times(
    eph, ts, location, t0, t1, tz: ZoneInfo
) -> tuple[datetime | None, datetime | None]:
    """Compute moonrise and moonset times."""
    moon = eph["Moon"]
    moonrise = moonset = None

    rise_times, rise_is_real = almanac.find_risings(location, moon, t0, t1)
    for t, is_real in zip(rise_times, rise_is_real, strict=False):
        if is_real:
            moonrise = t.utc_datetime().replace(tzinfo=UTC).astimezone(tz)
            break

    set_times, set_is_real = almanac.find_settings(location, moon, t0, t1)
    for t, is_real in zip(set_times, set_is_real, strict=False):
        if is_real:
            moonset = t.utc_datetime().replace(tzinfo=UTC).astimezone(tz)
            break

    return moonrise, moonset
