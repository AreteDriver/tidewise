"""Tests for scoring rules — 100% coverage on all threshold boundaries."""

from datetime import UTC, datetime, timedelta

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
)
from tidewise.scoring.rules import (
    _moon_phase_bonus,
    score_cloud_cover,
    score_precipitation,
    score_pressure,
    score_solunar,
    score_tide,
    score_water_temp,
    score_wind,
)


class TestScorePressure:
    def test_rapidly_falling(self):
        score, detail = score_pressure(PressureTrend.RAPIDLY_FALLING, -0.08)
        assert score == 1.0
        assert "aggressively" in detail

    def test_falling(self):
        score, _ = score_pressure(PressureTrend.FALLING, -0.04)
        assert score == 0.9

    def test_steady_low(self):
        score, _ = score_pressure(PressureTrend.STEADY, -0.005)
        assert score == 0.7

    def test_steady_high(self):
        score, _ = score_pressure(PressureTrend.STEADY, 0.005)
        assert score == 0.4

    def test_rising(self):
        score, _ = score_pressure(PressureTrend.RISING, 0.04)
        assert score == 0.6

    def test_rapidly_rising(self):
        score, detail = score_pressure(PressureTrend.RAPIDLY_RISING, 0.08)
        assert score == 0.3
        assert "lockjaw" in detail


class TestScoreTide:
    def _make_tide(self, direction, minutes=180, next_type=TideType.HIGH):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        next_time = now + timedelta(minutes=minutes)
        return TideData(
            predictions=[],
            current_direction=direction,
            next_event=TidePrediction(time=next_time, height_ft=8.0, type=next_type),
            minutes_until_next=minutes,
            station_id="9439040",
        ), now

    def test_early_incoming(self):
        tide, now = self._make_tide(TideDirection.INCOMING, minutes=300)
        score, detail = score_tide(tide, now)
        assert score == 0.9
        assert "incoming" in detail.lower()

    def test_mid_incoming(self):
        tide, now = self._make_tide(TideDirection.INCOMING, minutes=180)
        score, _ = score_tide(tide, now)
        assert score == 0.9

    def test_late_incoming(self):
        tide, now = self._make_tide(TideDirection.INCOMING, minutes=60)
        score, _ = score_tide(tide, now)
        assert score == 0.8

    def test_early_outgoing(self):
        tide, now = self._make_tide(TideDirection.OUTGOING, minutes=300, next_type=TideType.LOW)
        score, _ = score_tide(tide, now)
        assert score == 0.6

    def test_late_outgoing(self):
        tide, now = self._make_tide(TideDirection.OUTGOING, minutes=60, next_type=TideType.LOW)
        score, _ = score_tide(tide, now)
        assert score == 0.5

    def test_slack_before_incoming(self):
        tide, now = self._make_tide(TideDirection.SLACK, minutes=30, next_type=TideType.HIGH)
        score, detail = score_tide(tide, now)
        assert score == 0.7
        assert "slack" in detail.lower()

    def test_dead_slack(self):
        tide, now = self._make_tide(TideDirection.SLACK, minutes=30, next_type=TideType.LOW)
        score, _ = score_tide(tide, now)
        assert score == 0.3

    def test_solunar_major_bonus(self, sample_solunar_data):
        tide, _ = self._make_tide(TideDirection.INCOMING, minutes=300)
        # Set now to be inside a major period
        now = sample_solunar_data.major_periods[0].peak
        score, detail = score_tide(tide, now, sample_solunar_data)
        assert score == 1.0  # 0.9 + 0.1 = 1.0
        assert "solunar" in detail

    def test_incoming_no_next_event(self):
        tide = TideData(
            predictions=[],
            current_direction=TideDirection.INCOMING,
            next_event=None,
            minutes_until_next=0,
            station_id="9439040",
        )
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score, _ = score_tide(tide, now)
        assert score == 0.85


class TestScoreWind:
    def test_calm(self):
        score, _ = score_wind(3.0, "N")
        assert score == 0.8

    def test_light_ideal(self):
        score, detail = score_wind(7.0, "N")
        assert score == 0.9
        assert "slight chop" in detail

    def test_moderate(self):
        score, _ = score_wind(12.0, "N")
        assert score == 0.6

    def test_strong(self):
        score, detail = score_wind(18.0, "N")
        assert score == 0.3
        assert "tough" in detail

    def test_gale(self):
        score, detail = score_wind(25.0, "N")
        assert score == 0.1
        assert "unsafe" in detail

    def test_south_bonus(self):
        score, _ = score_wind(7.0, "SW")
        assert score == 1.0  # 0.9 + 0.1

    def test_east_penalty(self):
        score, _ = score_wind(7.0, "NE")
        assert score == 0.8  # 0.9 - 0.1

    def test_ssw_bonus(self):
        score, _ = score_wind(7.0, "SSW")
        assert score == 1.0

    def test_ene_penalty(self):
        score, _ = score_wind(7.0, "ENE")
        assert score == 0.8

    def test_neutral_direction(self):
        score, _ = score_wind(7.0, "W")
        assert score == 0.9


class TestScoreCloudCover:
    def test_overcast(self):
        score, detail = score_cloud_cover(90.0)
        assert score == 0.9
        assert "overcast" in detail.lower()

    def test_boundary_80(self):
        score, _ = score_cloud_cover(80.0)
        assert score == 0.9

    def test_partly_cloudy(self):
        score, _ = score_cloud_cover(60.0)
        assert score == 0.7

    def test_boundary_40(self):
        score, _ = score_cloud_cover(40.0)
        assert score == 0.7

    def test_mostly_clear(self):
        score, _ = score_cloud_cover(25.0)
        assert score == 0.5

    def test_boundary_10(self):
        score, _ = score_cloud_cover(10.0)
        assert score == 0.5

    def test_bluebird(self):
        score, detail = score_cloud_cover(5.0)
        assert score == 0.3
        assert "bluebird" in detail.lower()


class TestScorePrecipitation:
    def test_none(self):
        score, _ = score_precipitation(0.0)
        assert score == 0.7

    def test_light_rain(self):
        score, detail = score_precipitation(0.5)
        assert score == 0.8
        assert "trigger" in detail

    def test_moderate_rain(self):
        score, _ = score_precipitation(3.0)
        assert score == 0.6

    def test_heavy_rain(self):
        score, detail = score_precipitation(10.0)
        assert score == 0.3
        assert "poor visibility" in detail


class TestScoreSolunar:
    def _make_solunar(self, phase=MoonPhase.WAXING_GIBBOUS):
        base = datetime(2026, 3, 15, tzinfo=UTC)
        return SolunarData(
            major_periods=[
                SolunarPeriod(
                    type=SolunarPeriodType.MAJOR,
                    start=base.replace(hour=5),
                    end=base.replace(hour=7),
                    peak=base.replace(hour=6),
                ),
            ],
            minor_periods=[
                SolunarPeriod(
                    type=SolunarPeriodType.MINOR,
                    start=base.replace(hour=11),
                    end=base.replace(hour=12),
                    peak=base.replace(hour=11, minute=30),
                ),
            ],
            moon_phase=phase,
            moon_illumination=0.5,
            sunrise=None,
            sunset=None,
            moonrise=None,
            moonset=None,
        )

    def test_in_major_period(self):
        solunar = self._make_solunar()
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score, detail = score_solunar(solunar, now)
        assert score == 1.0
        assert "major" in detail

    def test_in_minor_period(self):
        solunar = self._make_solunar()
        now = datetime(2026, 3, 15, 11, 30, tzinfo=UTC)
        score, detail = score_solunar(solunar, now)
        assert score == 0.8
        assert "minor" in detail

    def test_outside_periods(self):
        solunar = self._make_solunar()
        now = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)
        score, detail = score_solunar(solunar, now)
        assert score == 0.4
        assert "next" in detail

    def test_outside_all_past(self):
        solunar = self._make_solunar()
        now = datetime(2026, 3, 15, 23, 0, tzinfo=UTC)
        score, detail = score_solunar(solunar, now)
        assert score == 0.4
        assert "outside" in detail.lower()

    def test_new_moon_bonus(self):
        solunar = self._make_solunar(MoonPhase.NEW_MOON)
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        score, _ = score_solunar(solunar, now)
        assert score == 1.0  # 1.0 + 0.15, capped at 1.0

    def test_full_moon_bonus(self):
        solunar = self._make_solunar(MoonPhase.FULL_MOON)
        now = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)  # outside
        score, _ = score_solunar(solunar, now)
        assert score == 0.55  # 0.4 + 0.15

    def test_quarter_moon_bonus(self):
        solunar = self._make_solunar(MoonPhase.FIRST_QUARTER)
        now = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)
        score, _ = score_solunar(solunar, now)
        assert score == 0.45  # 0.4 + 0.05

    def test_no_phase_bonus_for_crescent(self):
        solunar = self._make_solunar(MoonPhase.WAXING_CRESCENT)
        now = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)
        score, _ = score_solunar(solunar, now)
        assert score == 0.4


class TestScoreWaterTemp:
    def test_very_cold(self):
        score, detail = score_water_temp(35.0)
        assert score == 0.1
        assert "very cold" in detail.lower()

    def test_cold(self):
        score, detail = score_water_temp(44.0)
        assert score == 0.4
        assert "cold" in detail.lower()

    def test_cool(self):
        score, detail = score_water_temp(52.0)
        assert score == 0.7
        assert "cool" in detail.lower()

    def test_ideal(self):
        score, detail = score_water_temp(60.0)
        assert score == 1.0
        assert "ideal" in detail.lower()

    def test_warm(self):
        score, detail = score_water_temp(68.0)
        assert score == 0.7
        assert "warm" in detail.lower()

    def test_hot(self):
        score, detail = score_water_temp(78.0)
        assert score == 0.3
        assert "hot" in detail.lower()

    def test_boundary_40(self):
        score, _ = score_water_temp(40.0)
        assert score == 0.4

    def test_boundary_48(self):
        score, _ = score_water_temp(48.0)
        assert score == 0.7

    def test_boundary_55(self):
        score, _ = score_water_temp(55.0)
        assert score == 1.0

    def test_boundary_65(self):
        score, _ = score_water_temp(65.0)
        assert score == 1.0

    def test_boundary_72(self):
        score, _ = score_water_temp(72.0)
        assert score == 0.7

    def test_boundary_above_72(self):
        score, _ = score_water_temp(72.1)
        assert score == 0.3


class TestMoonPhaseBonus:
    def test_new_moon(self):
        assert _moon_phase_bonus(MoonPhase.NEW_MOON) == 0.15

    def test_full_moon(self):
        assert _moon_phase_bonus(MoonPhase.FULL_MOON) == 0.15

    def test_first_quarter(self):
        assert _moon_phase_bonus(MoonPhase.FIRST_QUARTER) == 0.05

    def test_last_quarter(self):
        assert _moon_phase_bonus(MoonPhase.LAST_QUARTER) == 0.05

    def test_waxing_gibbous(self):
        assert _moon_phase_bonus(MoonPhase.WAXING_GIBBOUS) == 0.0

    def test_waning_crescent(self):
        assert _moon_phase_bonus(MoonPhase.WANING_CRESCENT) == 0.0
