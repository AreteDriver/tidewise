"""Tests for notification system."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tidewise.config import NotificationConfig
from tidewise.models import FishingScore
from tidewise.notifications import (
    _load_state,
    _save_state,
    format_morning_summary,
    format_score_alert,
    send_desktop,
    send_notification,
    send_ntfy,
    should_notify,
    update_state,
)

# --- Fixtures ---


@pytest.fixture
def notif_config():
    return NotificationConfig(
        enabled=True,
        method="ntfy",
        ntfy_url="https://ntfy.sh",
        ntfy_topic="test-topic",
        alert_score=8.0,
        cooldown_minutes=60,
    )


@pytest.fixture
def high_score():
    return FishingScore(
        composite=8.5,
        factors=[],
        best_window_start=datetime(2026, 3, 15, 6, 0, tzinfo=UTC),
        best_window_end=datetime(2026, 3, 15, 8, 0, tzinfo=UTC),
        best_window_reason="Solunar major + incoming tide",
        suggestions=["Fish early morning", "Use topwater lures"],
    )


@pytest.fixture
def low_score():
    return FishingScore(
        composite=4.2,
        factors=[],
        best_window_start=None,
        best_window_end=None,
        best_window_reason="No ideal window",
        suggestions=[],
    )


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "state.json"


# --- send_ntfy ---


class TestSendNtfy:
    def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("tidewise.notifications.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                send_ntfy("https://ntfy.sh", "topic", "Title", "Body", "default", "fish")
            )

        assert result is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.args[0] == "https://ntfy.sh/topic"
        assert call_kwargs.kwargs["headers"]["Title"] == "Title"
        assert call_kwargs.kwargs["headers"]["Priority"] == "default"
        assert call_kwargs.kwargs["headers"]["Tags"] == "fish"

    def test_server_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("tidewise.notifications.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(send_ntfy("https://ntfy.sh", "topic", "T", "B"))

        assert result is False

    def test_network_error(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("tidewise.notifications.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(send_ntfy("https://ntfy.sh", "topic", "T", "B"))

        assert result is False

    def test_trailing_slash_stripped(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("tidewise.notifications.httpx.AsyncClient", return_value=mock_client):
            asyncio.run(send_ntfy("https://ntfy.sh/", "topic", "T", "B"))

        url_arg = mock_client.post.call_args.args[0]
        assert url_arg == "https://ntfy.sh/topic"


# --- send_desktop ---


class TestSendDesktop:
    def test_success(self):
        with patch("tidewise.notifications.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = send_desktop("Title", "Body")

        assert result is True
        mock_run.assert_called_once_with(
            ["notify-send", "Title", "Body"],
            capture_output=True,
            timeout=5,
        )

    def test_not_installed(self):
        with patch(
            "tidewise.notifications.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = send_desktop("Title", "Body")

        assert result is False

    def test_timeout(self):
        import subprocess

        with patch(
            "tidewise.notifications.subprocess.run",
            side_effect=subprocess.TimeoutExpired("notify-send", 5),
        ):
            result = send_desktop("Title", "Body")

        assert result is False

    def test_nonzero_exit(self):
        with patch("tidewise.notifications.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = send_desktop("Title", "Body")

        assert result is False


# --- send_notification ---


class TestSendNotification:
    def test_ntfy_method(self, notif_config):
        with patch("tidewise.notifications.send_ntfy", new_callable=AsyncMock) as mock:
            mock.return_value = True
            result = asyncio.run(send_notification(notif_config, "T", "B", "default", "fish"))

        assert result is True
        mock.assert_called_once()

    def test_desktop_method(self, notif_config):
        notif_config.method = "desktop"
        with patch("tidewise.notifications.send_desktop") as mock:
            mock.return_value = True
            result = asyncio.run(send_notification(notif_config, "T", "B"))

        assert result is True
        mock.assert_called_once_with("T", "B")

    def test_both_method(self, notif_config):
        notif_config.method = "both"
        with (
            patch("tidewise.notifications.send_ntfy", new_callable=AsyncMock) as mock_ntfy,
            patch("tidewise.notifications.send_desktop") as mock_desktop,
        ):
            mock_ntfy.return_value = True
            mock_desktop.return_value = True
            result = asyncio.run(send_notification(notif_config, "T", "B"))

        assert result is True
        mock_ntfy.assert_called_once()
        mock_desktop.assert_called_once()

    def test_none_method(self, notif_config):
        notif_config.method = "none"
        result = asyncio.run(send_notification(notif_config, "T", "B"))
        assert result is False

    def test_both_ntfy_fails_desktop_succeeds(self, notif_config):
        notif_config.method = "both"
        with (
            patch("tidewise.notifications.send_ntfy", new_callable=AsyncMock) as mock_ntfy,
            patch("tidewise.notifications.send_desktop") as mock_desktop,
        ):
            mock_ntfy.return_value = False
            mock_desktop.return_value = True
            result = asyncio.run(send_notification(notif_config, "T", "B"))

        assert result is True


# --- format_score_alert ---


class TestFormatScoreAlert:
    def test_with_window(self, high_score):
        title, body = format_score_alert(high_score, "Columbia River")
        assert "8.5/10" in title
        assert "Columbia River" in body
        assert "Best window" in body
        assert "Solunar major" in body

    def test_with_suggestions(self, high_score):
        title, body = format_score_alert(high_score, "Test Spot")
        assert "Fish early morning" in body
        assert "topwater" in body

    def test_without_window(self, low_score):
        title, body = format_score_alert(low_score, "Test Spot")
        assert "4.2/10" in title
        assert "Best window" not in body

    def test_with_timezone(self, high_score):
        title, body = format_score_alert(high_score, "Test Spot", tz_name="America/Los_Angeles")
        assert "PM" in body or "AM" in body

    def test_max_suggestions(self):
        score = FishingScore(
            composite=9.0,
            factors=[],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="",
            suggestions=["a", "b", "c", "d", "e"],
        )
        _, body = format_score_alert(score, "Spot")
        # Only first 3 suggestions in alert
        assert "- a" in body
        assert "- c" in body
        assert "- d" not in body


# --- format_morning_summary ---


class TestFormatMorningSummary:
    def test_basic(self, high_score):
        title, body = format_morning_summary(high_score, "Columbia River")
        assert "Morning" in title
        assert "8.5/10" in title
        assert "Columbia River" in body

    def test_with_factors(self):
        from tidewise.models import FactorScore

        score = FishingScore(
            composite=7.0,
            factors=[
                FactorScore(name="solunar", score=0.8, weight=0.25, detail="Major period"),
                FactorScore(name="tide", score=0.6, weight=0.25, detail="Incoming"),
            ],
            best_window_start=None,
            best_window_end=None,
            best_window_reason="",
        )
        _, body = format_morning_summary(score, "Spot")
        assert "solunar" in body
        assert "tide" in body
        assert "Major period" in body

    def test_with_window(self, high_score):
        _, body = format_morning_summary(high_score, "Spot", tz_name="UTC")
        assert "Best window" in body


# --- should_notify ---


class TestShouldNotify:
    def test_below_threshold(self, state_file):
        assert should_notify(7.0, 8.0, 60, state_file) is False

    def test_above_threshold_no_state(self, state_file):
        assert should_notify(8.5, 8.0, 60, state_file) is True

    def test_above_threshold_cooldown_active(self, state_file):
        state_file.write_text(json.dumps({"last_notified": datetime.now(UTC).isoformat()}))
        assert should_notify(8.5, 8.0, 60, state_file) is False

    def test_above_threshold_cooldown_expired(self, state_file):
        old_time = (datetime.now(UTC) - timedelta(minutes=120)).isoformat()
        state_file.write_text(json.dumps({"last_notified": old_time}))
        assert should_notify(8.5, 8.0, 60, state_file) is True

    def test_exact_threshold(self, state_file):
        assert should_notify(8.0, 8.0, 60, state_file) is True

    def test_corrupt_state_file(self, state_file):
        state_file.write_text("not json")
        assert should_notify(8.5, 8.0, 60, state_file) is True

    def test_invalid_timestamp_in_state(self, state_file):
        state_file.write_text(json.dumps({"last_notified": "garbage"}))
        assert should_notify(8.5, 8.0, 60, state_file) is True


# --- State file I/O ---


class TestStateIO:
    def test_save_and_load(self, state_file):
        data = {"last_notified": "2026-03-15T06:00:00+00:00", "last_score": 8.5}
        _save_state(state_file, data)
        loaded = _load_state(state_file)
        assert loaded == data

    def test_load_missing_file(self, tmp_path):
        result = _load_state(tmp_path / "missing.json")
        assert result == {}

    def test_load_corrupt_file(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid")
        result = _load_state(bad)
        assert result == {}

    def test_save_creates_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "state.json"
        _save_state(nested, {"key": "val"})
        assert nested.exists()
        assert _load_state(nested) == {"key": "val"}

    def test_update_state(self, state_file):
        update_state(8.5, state_file)
        loaded = _load_state(state_file)
        assert loaded["last_score"] == 8.5
        assert "last_notified" in loaded
