"""Tests for historical score tracking."""

import csv
from datetime import UTC, datetime, timedelta

import pytest

from tidewise.history import (
    export_csv,
    get_recent_scores,
    init_db,
    log_score,
    purge_old_records,
)
from tidewise.models import FactorScore, FishingScore


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_history.db"


@pytest.fixture
def sample_score():
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    return FishingScore(
        composite=7.5,
        factors=[
            FactorScore(name="solunar", score=0.8, weight=0.25, detail="Major period active"),
            FactorScore(name="tide", score=0.7, weight=0.25, detail="Incoming tide"),
            FactorScore(name="pressure", score=0.6, weight=0.20, detail="Falling slowly"),
        ],
        best_window_start=now.replace(hour=14),
        best_window_end=now.replace(hour=16),
        best_window_reason="Solunar major + incoming tide",
        suggestions=["Fish the incoming tide", "Target structure"],
    )


class TestInitDb:
    def test_creates_schema(self, db_path):
        result = init_db(db_path)
        assert result == db_path
        assert db_path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "history.db"
        init_db(nested)
        assert nested.exists()

    def test_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)  # should not raise
        assert db_path.exists()


class TestLogScore:
    def test_inserts_and_returns_true(self, db_path, sample_score):
        result = log_score(
            sample_score,
            "Astoria",
            "9439040",
            timestamp=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            db_path=db_path,
        )
        assert result is True

    def test_dedup_within_15_min_returns_false(self, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        assert log_score(sample_score, "Astoria", "9439040", ts, db_path) is True
        # 10 minutes later — should dedup
        ts2 = ts + timedelta(minutes=10)
        assert log_score(sample_score, "Astoria", "9439040", ts2, db_path) is False

    def test_dedup_after_15_min_returns_true(self, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        assert log_score(sample_score, "Astoria", "9439040", ts, db_path) is True
        # 20 minutes later — should log
        ts2 = ts + timedelta(minutes=20)
        assert log_score(sample_score, "Astoria", "9439040", ts2, db_path) is True

    def test_different_location_not_deduped(self, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        assert log_score(sample_score, "Astoria", "9439040", ts, db_path) is True
        assert log_score(sample_score, "Newport", "9435380", ts, db_path) is True

    def test_default_timestamp(self, db_path, sample_score):
        result = log_score(sample_score, "Astoria", "9439040", db_path=db_path)
        assert result is True

    def test_score_without_best_window(self, db_path):
        score = FishingScore(
            composite=3.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="No favorable window",
        )
        result = log_score(
            score,
            "Astoria",
            "9439040",
            timestamp=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
            db_path=db_path,
        )
        assert result is True


class TestGetRecentScores:
    def test_returns_correct_data(self, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)

        records = get_recent_scores(days=9999, db_path=db_path)
        assert len(records) == 1
        assert records[0]["composite"] == 7.5
        assert records[0]["location"] == "Astoria"
        assert records[0]["station_id"] == "9439040"

    def test_ordered_by_timestamp_desc(self, db_path, sample_score):
        ts1 = datetime(2026, 3, 15, 8, 0, tzinfo=UTC)
        ts2 = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        ts3 = datetime(2026, 3, 15, 16, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts1, db_path)
        log_score(sample_score, "Astoria", "9439040", ts2, db_path)
        log_score(sample_score, "Astoria", "9439040", ts3, db_path)

        records = get_recent_scores(days=9999, db_path=db_path)
        assert len(records) == 3
        assert records[0]["timestamp"] > records[1]["timestamp"]
        assert records[1]["timestamp"] > records[2]["timestamp"]

    def test_no_records_returns_empty(self, db_path):
        init_db(db_path)
        records = get_recent_scores(days=30, db_path=db_path)
        assert records == []

    def test_missing_db_returns_empty(self, tmp_path):
        records = get_recent_scores(days=30, db_path=tmp_path / "nonexistent.db")
        assert records == []

    def test_location_filter(self, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)
        ts2 = ts + timedelta(hours=1)
        log_score(sample_score, "Newport", "9435380", ts2, db_path)

        astoria = get_recent_scores(days=9999, location="Astoria", db_path=db_path)
        assert len(astoria) == 1
        assert astoria[0]["location"] == "Astoria"

    def test_factors_round_trip_as_json(self, db_path, sample_score):
        import json

        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)

        records = get_recent_scores(days=9999, db_path=db_path)
        factors = json.loads(records[0]["factors"])
        assert len(factors) == 3
        assert factors[0]["name"] == "solunar"
        assert factors[0]["score"] == 0.8

    def test_suggestions_round_trip_as_json(self, db_path, sample_score):
        import json

        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)

        records = get_recent_scores(days=9999, db_path=db_path)
        suggestions = json.loads(records[0]["suggestions"])
        assert "Fish the incoming tide" in suggestions


class TestExportCsv:
    def test_writes_correct_headers_and_data(self, tmp_path, db_path, sample_score):
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)
        records = get_recent_scores(days=9999, db_path=db_path)

        out = tmp_path / "export.csv"
        result = export_csv(records, out)
        assert result == out
        assert out.exists()

        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["composite"] == "7.5"
        assert rows[0]["location"] == "Astoria"
        assert rows[0]["station_id"] == "9439040"
        assert "factors" not in reader.fieldnames
        assert "suggestions" not in reader.fieldnames

    def test_empty_records_writes_headers_only(self, tmp_path):
        out = tmp_path / "empty.csv"
        export_csv([], out)

        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows == []
        assert "timestamp" in reader.fieldnames
        assert "composite" in reader.fieldnames

    def test_handles_none_best_window(self, tmp_path, db_path):
        score = FishingScore(
            composite=3.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="No favorable window",
        )
        ts = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
        log_score(score, "Astoria", "9439040", ts, db_path)
        records = get_recent_scores(days=9999, db_path=db_path)

        out = tmp_path / "none_window.csv"
        export_csv(records, out)

        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["best_window_start"] == ""
        assert rows[0]["best_window_end"] == ""
        assert rows[0]["best_window_reason"] == "No favorable window"


class TestPurgeOldRecords:
    def test_deletes_old_keeps_recent(self, db_path, sample_score):
        old_ts = datetime.now(UTC) - timedelta(days=400)
        recent_ts = datetime.now(UTC) - timedelta(hours=1)
        log_score(sample_score, "Astoria", "9439040", old_ts, db_path)
        log_score(sample_score, "Astoria", "9439040", recent_ts, db_path)

        deleted = purge_old_records(retention_days=365, db_path=db_path)
        assert deleted == 1

        remaining = get_recent_scores(days=9999, db_path=db_path)
        assert len(remaining) == 1

    def test_missing_db_returns_zero(self, tmp_path):
        result = purge_old_records(db_path=tmp_path / "nonexistent.db")
        assert result == 0

    def test_nothing_to_purge(self, db_path, sample_score):
        ts = datetime.now(UTC) - timedelta(hours=1)
        log_score(sample_score, "Astoria", "9439040", ts, db_path)
        deleted = purge_old_records(retention_days=365, db_path=db_path)
        assert deleted == 0
