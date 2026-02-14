"""Tests for composite scoring engine."""

from datetime import UTC, datetime

from tidewise.config import ScoreWeights
from tidewise.scoring.engine import _find_best_window, calculate_score


class TestCalculateScore:
    def test_composite_score_range(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        assert 1.0 <= result.composite <= 10.0

    def test_all_factors_present(self, sample_tide_data, sample_weather_data, sample_solunar_data):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        factor_names = {f.name for f in result.factors}
        assert factor_names == {"solunar", "tide", "pressure", "wind", "cloud", "precipitation"}

    def test_weights_affect_composite(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        # Default weights
        result1 = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        # Heavily weight solunar
        heavy_solunar = ScoreWeights(
            solunar=0.80,
            tide=0.05,
            pressure=0.05,
            wind=0.05,
            cloud=0.03,
            precipitation=0.02,
        )
        result2 = calculate_score(
            heavy_solunar,
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        # Scores should differ with different weights
        assert result1.composite != result2.composite

    def test_suggestions_generated(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        assert isinstance(result.suggestions, list)
        assert len(result.suggestions) <= 5

    def test_best_window_set(self, sample_tide_data, sample_weather_data, sample_solunar_data):
        now = datetime(2026, 3, 15, 4, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        assert result.best_window_reason != ""

    def test_seven_factors_with_water_temp(
        self, sample_tide_data, sample_weather_data, sample_solunar_data, sample_water_temp_data
    ):
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
            water_temp=sample_water_temp_data,
        )
        factor_names = {f.name for f in result.factors}
        assert "water_temp" in factor_names
        assert len(result.factors) == 7

    def test_six_factors_without_water_temp(
        self, sample_tide_data, sample_weather_data, sample_solunar_data
    ):
        """Backward compat — no water temp data, 6 factors."""
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
        )
        factor_names = {f.name for f in result.factors}
        assert "water_temp" not in factor_names
        assert len(result.factors) == 6

    def test_weight_normalization(
        self, sample_tide_data, sample_weather_data, sample_solunar_data, sample_water_temp_data
    ):
        """Weights summing to != 1.0 still produce valid 1-10 score."""
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        # Default weights sum to 1.10 with water_temp
        result = calculate_score(
            ScoreWeights(),
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
            water_temp=sample_water_temp_data,
        )
        assert 1.0 <= result.composite <= 10.0

    def test_water_temp_zero_weight_excluded(
        self, sample_tide_data, sample_weather_data, sample_solunar_data, sample_water_temp_data
    ):
        """Water temp with weight=0 should not appear in factors."""
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        weights = ScoreWeights(water_temp=0.0)
        result = calculate_score(
            weights,
            sample_tide_data,
            sample_weather_data,
            sample_solunar_data,
            now,
            water_temp=sample_water_temp_data,
        )
        factor_names = {f.name for f in result.factors}
        assert "water_temp" not in factor_names


class TestFindBestWindow:
    def test_upcoming_major_period(self, sample_tide_data, sample_solunar_data):
        now = datetime(2026, 3, 15, 4, 0, tzinfo=UTC)  # before first major
        start, end, reason = _find_best_window(sample_tide_data, sample_solunar_data, now)
        assert start is not None
        assert "solunar" in reason.lower() or "major" in reason.lower()

    def test_currently_in_major(self, sample_tide_data, sample_solunar_data):
        now = sample_solunar_data.major_periods[0].peak
        start, end, reason = _find_best_window(sample_tide_data, sample_solunar_data, now)
        assert "currently" in reason.lower()

    def test_fallback_incoming_tide(self, sample_tide_data, sample_solunar_data):
        # Set now after all solunar periods
        now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)
        start, _, reason = _find_best_window(sample_tide_data, sample_solunar_data, now)
        assert "tide" in reason.lower() or "incoming" in reason.lower()
