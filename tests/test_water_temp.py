"""Tests for NOAA water temperature source."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tidewise.sources.water_temp import fetch_water_temp, fetch_water_temp_sync

VALID_RESPONSE = {
    "metadata": {"id": "9439040", "name": "Astoria"},
    "data": [{"t": "2026-03-15 05:30", "v": "52.0", "f": "0,0,0"}],
}


class TestFetchWaterTemp:
    @pytest.mark.asyncio
    async def test_parse_valid_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = VALID_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_water_temp("9439040", client=mock_client)
        assert result is not None
        assert result.temperature_f == 52.0
        assert result.station_id == "9439040"
        assert result.timestamp == datetime(2026, 3, 15, 5, 30, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_missing_data_returns_none(self):
        """Station without temp sensor returns error."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": {"message": "No data was found."}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_water_temp("0000000", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await fetch_water_temp("9439040", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_response_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"bad": "format"}]}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_water_temp("9439040", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_data_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_water_temp("9439040", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_data_key_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"metadata": {}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_water_temp("9439040", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_client_when_none(self):
        with patch("tidewise.sources.water_temp.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = VALID_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            mock_cls.return_value = mock_client

            result = await fetch_water_temp("9439040")
            assert result is not None
            mock_client.aclose.assert_awaited_once()


class TestFetchWaterTempSync:
    def test_sync_wrapper(self):
        with patch("tidewise.sources.water_temp.asyncio.run") as mock_run:
            mock_run.return_value = None
            result = fetch_water_temp_sync("9439040")
            assert result is None
            mock_run.assert_called_once()
