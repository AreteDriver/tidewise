"""Notification system — ntfy.sh push + desktop alerts."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from tidewise.config import NotificationConfig
from tidewise.models import FishingScore

_STATE_DIR = Path.home() / ".local" / "share" / "tidewise"
_STATE_FILE = _STATE_DIR / "notify_state.json"


async def send_ntfy(
    url: str,
    topic: str,
    title: str,
    message: str,
    priority: str = "default",
    tags: str = "fish",
) -> bool:
    """POST notification to ntfy.sh. Returns True on success."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{url.rstrip('/')}/{topic}",
                content=message,
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": tags,
                },
                timeout=10.0,
            )
            return resp.status_code == 200
    except httpx.HTTPError:
        return False


def send_desktop(title: str, message: str) -> bool:
    """Send desktop notification via notify-send. Returns True on success."""
    try:
        result = subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def send_notification(
    config: NotificationConfig,
    title: str,
    message: str,
    priority: str = "default",
    tags: str = "fish",
) -> bool:
    """Dispatch notification based on config.method."""
    if config.method == "none":
        return False

    sent = False
    if config.method in ("ntfy", "both"):
        sent = await send_ntfy(config.ntfy_url, config.ntfy_topic, title, message, priority, tags)
    if config.method in ("desktop", "both"):
        desktop_ok = send_desktop(title, message)
        sent = sent or desktop_ok

    return sent


def format_score_alert(
    score: FishingScore, location_name: str, tz_name: str | None = None
) -> tuple[str, str]:
    """Format a score threshold alert. Returns (title, body)."""
    title = f"TideWise: {score.composite:.1f}/10"
    lines = [f"Location: {location_name}"]

    if score.best_window_start and score.best_window_end:
        start = _to_local(score.best_window_start, tz_name)
        end = _to_local(score.best_window_end, tz_name)
        lines.append(f"Best window: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}")
    if score.best_window_reason:
        lines.append(f"Reason: {score.best_window_reason}")

    if score.suggestions:
        lines.append("")
        for s in score.suggestions[:3]:
            lines.append(f"- {s}")

    return title, "\n".join(lines)


def format_morning_summary(
    score: FishingScore, location_name: str, tz_name: str | None = None
) -> tuple[str, str]:
    """Format a morning summary notification. Returns (title, body)."""
    title = f"TideWise Morning: {score.composite:.1f}/10"
    lines = [f"Location: {location_name}"]

    # Factor breakdown
    for factor in score.factors:
        lines.append(f"  {factor.name}: {factor.score:.2f} - {factor.detail}")

    if score.best_window_start and score.best_window_end:
        start = _to_local(score.best_window_start, tz_name)
        end = _to_local(score.best_window_end, tz_name)
        lines.append(f"\nBest window: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}")

    if score.suggestions:
        lines.append("")
        for s in score.suggestions[:3]:
            lines.append(f"- {s}")

    return title, "\n".join(lines)


def should_notify(
    score_value: float,
    threshold: float,
    cooldown_minutes: int,
    state_file: Path | None = None,
) -> bool:
    """Check if notification should fire: score >= threshold AND cooldown elapsed."""
    if score_value < threshold:
        return False

    path = state_file or _STATE_FILE
    state = _load_state(path)
    last = state.get("last_notified")
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.now(UTC) - last_dt < timedelta(minutes=cooldown_minutes):
                return False
        except (ValueError, TypeError):
            pass

    return True


def update_state(score_value: float, state_file: Path | None = None) -> None:
    """Record that a notification was sent."""
    path = state_file or _STATE_FILE
    _save_state(
        path,
        {
            "last_notified": datetime.now(UTC).isoformat(),
            "last_score": score_value,
        },
    )


def _load_state(path: Path) -> dict:
    """Load notification state from JSON file."""
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(path: Path, data: dict) -> None:
    """Save notification state to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _to_local(dt: datetime, tz_name: str | None) -> datetime:
    """Convert a datetime to local timezone if tz_name provided."""
    if tz_name and dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo(tz_name))
    return dt
