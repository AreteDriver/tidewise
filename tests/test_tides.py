"""Tests for NOAA tides client."""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from tidewise.models import TideDirection, TideType
from tidewise.sources.tides import (
    NOAA_BASE_URL,
    TideAPIError,
    _determine_tide_direction,
    _find_next_event,
    _parse_predictions,
    fetch_tides,
)

# Reusable mock response
NOAA_RESPONSE = {
    "predictions": [
        {"t": "2026-03-15 03:22", "v": "1.200", "type": "L"},
        {"t": "2026-03-15 09:45", "v": "8.100", "type": "H"},
        {"t": "2026-03-15 15:58", "v": "2.300", "type": "L"},
        {"t": "2026-03-15 22:10", "v": "7.500", "type": "H"},
    ]
}


class TestParsePredictions:
    def test_basic_parsing(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        assert len(preds) == 4
        assert preds[0].type == TideType.LOW
        assert preds[0].height_ft == 1.2
        assert preds[1].type == TideType.HIGH
        assert preds[1].height_ft == 8.1

    def test_time_parsing(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        assert preds[0].time.hour == 3
        assert preds[0].time.minute == 22

    def test_malformed_entry_raises(self):
        with pytest.raises(TideAPIError, match="Malformed"):
            _parse_predictions([{"t": "bad-date", "v": "1.0", "type": "H"}])

    def test_missing_key_raises(self):
        with pytest.raises(TideAPIError, match="Malformed"):
            _parse_predictions([{"t": "2026-03-15 09:45", "type": "H"}])


class TestTideDirection:
    def test_incoming_between_low_and_high(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)  # between low@3:22 and high@9:45
        assert _determine_tide_direction(preds, now) == TideDirection.INCOMING

    def test_outgoing_between_high_and_low(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)  # between high@9:45 and low@15:58
        assert _determine_tide_direction(preds, now) == TideDirection.OUTGOING

    def test_slack_near_event(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 9, 30, tzinfo=UTC)  # 15 min before high@9:45
        assert _determine_tide_direction(preds, now) == TideDirection.SLACK

    def test_slack_at_event(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 9, 45, tzinfo=UTC)  # exactly at high
        assert _determine_tide_direction(preds, now) == TideDirection.SLACK

    def test_empty_predictions(self):
        assert _determine_tide_direction([], datetime.now(UTC)) == TideDirection.SLACK

    def test_before_first_prediction(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 0, 0, tzinfo=UTC)  # before first event
        result = _determine_tide_direction(preds, now)
        assert result in (TideDirection.INCOMING, TideDirection.OUTGOING)


class TestFindNextEvent:
    def test_finds_next_high(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 6, 0, tzinfo=UTC)
        event, minutes = _find_next_event(preds, now)
        assert event is not None
        assert event.type == TideType.HIGH
        assert event.time.hour == 9
        assert minutes == 225  # 3h45m

    def test_finds_next_low(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 10, 0, tzinfo=UTC)
        event, minutes = _find_next_event(preds, now)
        assert event is not None
        assert event.type == TideType.LOW

    def test_no_future_event(self):
        preds = _parse_predictions(NOAA_RESPONSE["predictions"])
        now = datetime(2026, 3, 15, 23, 0, tzinfo=UTC)  # after all events
        event, minutes = _find_next_event(preds, now)
        assert event is None
        assert minutes == 0


class TestFetchTides:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        respx.get(NOAA_BASE_URL).mock(return_value=httpx.Response(200, json=NOAA_RESPONSE))
        result = await fetch_tides(
            "9439040",
            datetime(2026, 3, 15),
            now=datetime(2026, 3, 15, 6, 0, tzinfo=UTC),
        )
        assert result.station_id == "9439040"
        assert len(result.predictions) == 4
        assert result.current_direction == TideDirection.INCOMING
        assert result.next_event is not None

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_response(self):
        respx.get(NOAA_BASE_URL).mock(
            return_value=httpx.Response(
                200,
                json={"error": {"message": "Station not found"}},
            )
        )
        with pytest.raises(TideAPIError, match="Station not found"):
            await fetch_tides("0000000", datetime(2026, 3, 15))

    @respx.mock
    @pytest.mark.asyncio
    async def test_missing_predictions_key(self):
        respx.get(NOAA_BASE_URL).mock(return_value=httpx.Response(200, json={"data": []}))
        with pytest.raises(TideAPIError, match="missing 'predictions'"):
            await fetch_tides("9439040", datetime(2026, 3, 15))

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error(self):
        respx.get(NOAA_BASE_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(TideAPIError, match="request failed"):
            await fetch_tides("9439040", datetime(2026, 3, 15))

    @respx.mock
    @pytest.mark.asyncio
    async def test_multi_day_fetch(self):
        resp = {
            "predictions": NOAA_RESPONSE["predictions"]
            + [
                {"t": "2026-03-16 04:15", "v": "1.5", "type": "L"},
                {"t": "2026-03-16 10:30", "v": "7.8", "type": "H"},
            ]
        }
        respx.get(NOAA_BASE_URL).mock(return_value=httpx.Response(200, json=resp))
        result = await fetch_tides(
            "9439040",
            datetime(2026, 3, 15),
            days=2,
            now=datetime(2026, 3, 15, 6, 0, tzinfo=UTC),
        )
        assert len(result.predictions) == 6

    @respx.mock
    @pytest.mark.asyncio
    async def test_with_provided_client(self):
        respx.get(NOAA_BASE_URL).mock(return_value=httpx.Response(200, json=NOAA_RESPONSE))
        async with httpx.AsyncClient() as client:
            result = await fetch_tides(
                "9439040",
                datetime(2026, 3, 15),
                now=datetime(2026, 3, 15, 6, 0, tzinfo=UTC),
                client=client,
            )
            assert len(result.predictions) == 4
