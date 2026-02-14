"""Tests for solunar engine — mocked skyfield to avoid downloading ephemeris."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from tidewise.models import MoonPhase, SolunarPeriodType
from tidewise.sources.solunar import (
    _compute_moon_illumination,
    _compute_moon_phase,
    _phase_angle_to_name,
    get_solunar_data,
)


class TestPhaseAngleMapping:
    """Test all 8 moon phase mappings (45-degree segments)."""

    @pytest.mark.parametrize(
        "angle,expected",
        [
            (0, MoonPhase.NEW_MOON),
            (10, MoonPhase.NEW_MOON),
            (22, MoonPhase.NEW_MOON),
            (350, MoonPhase.NEW_MOON),
            (45, MoonPhase.WAXING_CRESCENT),
            (60, MoonPhase.WAXING_CRESCENT),
            (90, MoonPhase.FIRST_QUARTER),
            (100, MoonPhase.FIRST_QUARTER),
            (135, MoonPhase.WAXING_GIBBOUS),
            (150, MoonPhase.WAXING_GIBBOUS),
            (180, MoonPhase.FULL_MOON),
            (200, MoonPhase.FULL_MOON),
            (225, MoonPhase.WANING_GIBBOUS),
            (240, MoonPhase.WANING_GIBBOUS),
            (270, MoonPhase.LAST_QUARTER),
            (290, MoonPhase.LAST_QUARTER),
            (315, MoonPhase.WANING_CRESCENT),
            (330, MoonPhase.WANING_CRESCENT),
        ],
    )
    def test_phase_angle(self, angle, expected):
        assert _phase_angle_to_name(angle) == expected

    def test_phase_boundary_22_5(self):
        assert _phase_angle_to_name(22.5) == MoonPhase.WAXING_CRESCENT

    def test_phase_boundary_337_5(self):
        assert _phase_angle_to_name(337.5) == MoonPhase.NEW_MOON

    def test_phase_angle_wraps(self):
        assert _phase_angle_to_name(360) == MoonPhase.NEW_MOON
        assert _phase_angle_to_name(405) == MoonPhase.WAXING_CRESCENT


class TestMoonIllumination:
    def test_new_moon_illumination(self):
        mock_angle = MagicMock()
        mock_angle.degrees = 0.0
        with patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle):
            result = _compute_moon_illumination(MagicMock(), MagicMock(), datetime(2026, 1, 1, tzinfo=timezone.utc))
            assert result == 0.0

    def test_full_moon_illumination(self):
        mock_angle = MagicMock()
        mock_angle.degrees = 180.0
        with patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle):
            result = _compute_moon_illumination(MagicMock(), MagicMock(), datetime(2026, 1, 1, tzinfo=timezone.utc))
            assert result == 1.0

    def test_quarter_illumination(self):
        mock_angle = MagicMock()
        mock_angle.degrees = 90.0
        with patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle):
            result = _compute_moon_illumination(MagicMock(), MagicMock(), datetime(2026, 1, 1, tzinfo=timezone.utc))
            assert result == 0.5


class TestComputeMoonPhase:
    def test_returns_phase_from_ephemeris(self):
        mock_angle = MagicMock()
        mock_angle.degrees = 180.0
        with patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle):
            result = _compute_moon_phase(MagicMock(), MagicMock(), datetime(2026, 1, 1, tzinfo=timezone.utc))
            assert result == MoonPhase.FULL_MOON


def _make_skyfield_time(dt: datetime):
    """Create a mock skyfield time object."""
    mock = MagicMock()
    mock.utc_datetime.return_value = dt.replace(tzinfo=None)
    return mock


class TestGetSolunarData:
    """Integration test with fully mocked skyfield."""

    def _build_mocks(self):
        eph = MagicMock()
        ts = MagicMock()
        ts.from_datetime.return_value = MagicMock()

        mock_angle = MagicMock()
        mock_angle.degrees = 135.0  # waxing gibbous

        base_utc = datetime(2026, 3, 15, 8, 0, 0)

        # Meridian transits (2 events)
        transit_times = [
            _make_skyfield_time(base_utc.replace(hour=6)),
            _make_skyfield_time(base_utc.replace(hour=18)),
        ]
        transit_events = [0, 1]

        # Rise/set times
        rise_time = _make_skyfield_time(base_utc.replace(hour=15))
        set_time = _make_skyfield_time(base_utc.replace(hour=4))
        sunrise_time = _make_skyfield_time(base_utc.replace(hour=14, minute=20))
        sunset_time = _make_skyfield_time(base_utc.replace(hour=1, minute=30))

        return (eph, ts, mock_angle, transit_times, transit_events,
                rise_time, set_time, sunrise_time, sunset_time)

    @patch("tidewise.sources.solunar._get_ephemeris")
    def test_full_solunar_calculation(self, mock_get_eph):
        (eph, ts, mock_angle, transit_times, transit_events,
         rise_time, set_time, sunrise_time, sunset_time) = self._build_mocks()
        mock_get_eph.return_value = (eph, ts)

        with (
            patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle),
            patch("tidewise.sources.solunar.almanac.meridian_transits") as mock_meridian,
            patch("tidewise.sources.solunar.almanac.find_discrete",
                  return_value=(transit_times, transit_events)),
            patch("tidewise.sources.solunar.almanac.find_risings") as mock_find_risings,
            patch("tidewise.sources.solunar.almanac.find_settings") as mock_find_settings,
        ):
            # find_risings/find_settings are called for moon (minor), sun, moon (rise/set times)
            # moon rise (minor), sun rise, moon rise (times)
            mock_find_risings.side_effect = [
                ([rise_time], [True]),   # moon rise (minor periods)
                ([sunrise_time], [True]),  # sun rise
                ([rise_time], [True]),   # moon rise (times)
            ]
            # moon set (minor), sun set, moon set (times)
            mock_find_settings.side_effect = [
                ([set_time], [True]),    # moon set (minor periods)
                ([sunset_time], [True]),   # sun set
                ([set_time], [True]),    # moon set (times)
            ]

            result = get_solunar_data(
                latitude=46.1879,
                longitude=-123.8313,
                date=datetime(2026, 3, 15),
                tz_name="America/Los_Angeles",
            )

            assert result.moon_phase == MoonPhase.WAXING_GIBBOUS
            assert 0.0 <= result.moon_illumination <= 1.0
            assert len(result.major_periods) == 2
            for p in result.major_periods:
                assert p.type == SolunarPeriodType.MAJOR
                assert (p.end - p.start) == timedelta(hours=2)
            assert len(result.minor_periods) == 2
            assert result.sunrise is not None
            assert result.sunset is not None
            assert result.moonrise is not None
            assert result.moonset is not None

    @patch("tidewise.sources.solunar._get_ephemeris")
    def test_no_moonrise_edge_case(self, mock_get_eph):
        """Handle days with no moonrise (e.g. polar regions)."""
        (eph, ts, mock_angle, transit_times, transit_events,
         _, _, sunrise_time, sunset_time) = self._build_mocks()
        mock_get_eph.return_value = (eph, ts)

        with (
            patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle),
            patch("tidewise.sources.solunar.almanac.meridian_transits"),
            patch("tidewise.sources.solunar.almanac.find_discrete",
                  return_value=(transit_times, transit_events)),
            patch("tidewise.sources.solunar.almanac.find_risings") as mock_find_risings,
            patch("tidewise.sources.solunar.almanac.find_settings") as mock_find_settings,
        ):
            mock_find_risings.side_effect = [
                ([], []),              # moon rise (minor) — none
                ([sunrise_time], [True]),  # sun rise
                ([], []),              # moon rise (times) — none
            ]
            mock_find_settings.side_effect = [
                ([], []),              # moon set (minor) — none
                ([sunset_time], [True]),   # sun set
                ([], []),              # moon set (times) — none
            ]

            result = get_solunar_data(
                latitude=46.1879,
                longitude=-123.8313,
                date=datetime(2026, 3, 15),
                tz_name="America/Los_Angeles",
            )

            assert len(result.minor_periods) == 0
            assert result.moonrise is None
            assert result.moonset is None

    @patch("tidewise.sources.solunar._get_ephemeris")
    def test_minor_periods_duration(self, mock_get_eph):
        """Minor periods should be ~1h (30min each side)."""
        (eph, ts, mock_angle, _, _,
         rise_time, set_time, sunrise_time, sunset_time) = self._build_mocks()
        mock_get_eph.return_value = (eph, ts)

        with (
            patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle),
            patch("tidewise.sources.solunar.almanac.meridian_transits"),
            patch("tidewise.sources.solunar.almanac.find_discrete",
                  return_value=([], [])),  # no major transits
            patch("tidewise.sources.solunar.almanac.find_risings") as mock_find_risings,
            patch("tidewise.sources.solunar.almanac.find_settings") as mock_find_settings,
        ):
            mock_find_risings.side_effect = [
                ([rise_time], [True]),
                ([sunrise_time], [True]),
                ([rise_time], [True]),
            ]
            mock_find_settings.side_effect = [
                ([set_time], [True]),
                ([sunset_time], [True]),
                ([set_time], [True]),
            ]

            result = get_solunar_data(
                latitude=46.1879,
                longitude=-123.8313,
                date=datetime(2026, 3, 15),
                tz_name="America/Los_Angeles",
            )

            assert len(result.major_periods) == 0
            for p in result.minor_periods:
                assert p.type == SolunarPeriodType.MINOR
                assert (p.end - p.start) == timedelta(hours=1)

    @patch("tidewise.sources.solunar._get_ephemeris")
    def test_non_real_risings_filtered(self, mock_get_eph):
        """Non-real horizon crossings (transits without touching horizon) are filtered."""
        (eph, ts, mock_angle, transit_times, transit_events,
         rise_time, set_time, sunrise_time, sunset_time) = self._build_mocks()
        mock_get_eph.return_value = (eph, ts)

        with (
            patch("tidewise.sources.solunar.almanac.moon_phase", return_value=mock_angle),
            patch("tidewise.sources.solunar.almanac.meridian_transits"),
            patch("tidewise.sources.solunar.almanac.find_discrete",
                  return_value=([], [])),
            patch("tidewise.sources.solunar.almanac.find_risings") as mock_find_risings,
            patch("tidewise.sources.solunar.almanac.find_settings") as mock_find_settings,
        ):
            # is_real=False means it's a transit, not a real crossing
            mock_find_risings.side_effect = [
                ([rise_time], [False]),    # moon rise — not real
                ([sunrise_time], [False]),   # sun rise — not real
                ([rise_time], [False]),    # moon rise time — not real
            ]
            mock_find_settings.side_effect = [
                ([set_time], [False]),
                ([sunset_time], [False]),
                ([set_time], [False]),
            ]

            result = get_solunar_data(
                latitude=46.1879,
                longitude=-123.8313,
                date=datetime(2026, 3, 15),
                tz_name="America/Los_Angeles",
            )

            assert len(result.minor_periods) == 0
            assert result.sunrise is None
            assert result.sunset is None
            assert result.moonrise is None
            assert result.moonset is None
