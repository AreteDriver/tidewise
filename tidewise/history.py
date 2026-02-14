"""Historical score tracking — SQLite storage for trend analysis."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tidewise.models import FishingScore

_DATA_DIR = Path.home() / ".local" / "share" / "tidewise"
_DB_FILE = _DATA_DIR / "history.db"

_DEDUP_MINUTES = 15

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    location TEXT NOT NULL,
    station_id TEXT NOT NULL,
    composite REAL NOT NULL,
    factors TEXT,
    best_window_start TEXT,
    best_window_end TEXT,
    best_window_reason TEXT,
    suggestions TEXT
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_scores_ts ON scores(timestamp)
"""


def init_db(db_path: Path | None = None) -> Path:
    """Create database schema if it doesn't exist. Returns the db path used."""
    db_path = db_path or _DB_FILE
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(_CREATE_TABLE)
        conn.execute(_CREATE_INDEX)
        conn.commit()
    finally:
        conn.close()
    return db_path


def log_score(
    score: FishingScore,
    location: str,
    station_id: str,
    timestamp: datetime | None = None,
    db_path: Path | None = None,
) -> bool:
    """Log a score to history. Returns True if logged, False if deduped."""
    db_path = db_path or _DB_FILE
    init_db(db_path)

    if timestamp is None:
        timestamp = datetime.now(UTC)
    ts_iso = timestamp.isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        # Dedup: skip if same location/station has entry within DEDUP_MINUTES
        cutoff = (timestamp - timedelta(minutes=_DEDUP_MINUTES)).isoformat()
        row = conn.execute(
            "SELECT id FROM scores "
            "WHERE location = ? AND station_id = ? AND timestamp > ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (location, station_id, cutoff),
        ).fetchone()

        if row is not None:
            return False

        factors_json = json.dumps(
            [
                {"name": f.name, "score": f.score, "weight": f.weight, "detail": f.detail}
                for f in score.factors
            ]
        )
        suggestions_json = json.dumps(score.suggestions)

        conn.execute(
            "INSERT INTO scores "
            "(timestamp, location, station_id, composite, factors, "
            "best_window_start, best_window_end, best_window_reason, suggestions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ts_iso,
                location,
                station_id,
                score.composite,
                factors_json,
                score.best_window_start.isoformat() if score.best_window_start else None,
                score.best_window_end.isoformat() if score.best_window_end else None,
                score.best_window_reason,
                suggestions_json,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_recent_scores(
    days: int = 30,
    location: str | None = None,
    db_path: Path | None = None,
) -> list[dict]:
    """Get recent score records ordered by timestamp descending."""
    db_path = db_path or _DB_FILE
    if not db_path.exists():
        return []

    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if location:
            rows = conn.execute(
                "SELECT * FROM scores WHERE timestamp > ? AND location = ? ORDER BY timestamp DESC",
                (cutoff, location),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM scores WHERE timestamp > ? ORDER BY timestamp DESC",
                (cutoff,),
            ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


def purge_old_records(retention_days: int = 365, db_path: Path | None = None) -> int:
    """Delete records older than retention_days. Returns count deleted."""
    db_path = db_path or _DB_FILE
    if not db_path.exists():
        return 0

    cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).isoformat()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("DELETE FROM scores WHERE timestamp < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
