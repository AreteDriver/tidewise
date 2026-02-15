"""Tests for USGS Water Services source."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tidewise.sources.usgs import fetch_usgs_gauge, fetch_usgs_gauge_sync

VALID_RESPONSE = {
    "value": {
        "timeSeries": [
            {
                "variable": {"variableCode": [{"value": "00060"}]},
                "values": [
                    {
                        "value": [
                            {
                                "value": "12500",
                                "dateTime": "2026-03-15T06:00:00.000-00:00",
                            }
                        ]
                    }
                ],
            },
            {
                "variable": {"variableCode": [{"value": "00065"}]},
                "values": [
                    {
                        "value": [
                            {
                                "value": "8.45",
                                "dateTime": "2026-03-15T06:00:00.000-00:00",
                            }
                        ]
                    }
                ],
            },
        ]
    }
}


class TestFetchUSGSGauge:
    @pytest.mark.asyncio
    async def test_parse_valid_response(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = VALID_RESPONSE
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is not None
        assert result.discharge_cfs == 12500.0
        assert result.gauge_height_ft == 8.45
        assert result.gauge_id == "14246900"
        assert result.timestamp == datetime(2026, 3, 15, 6, 0, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_discharge_only(self):
        """Station with discharge but no gauge height."""
        response = {
            "value": {
                "timeSeries": [
                    {
                        "variable": {"variableCode": [{"value": "00060"}]},
                        "values": [
                            {
                                "value": [
                                    {
                                        "value": "5000",
                                        "dateTime": "2026-03-15T06:00:00.000",
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is not None
        assert result.discharge_cfs == 5000.0
        assert result.gauge_height_ft is None

    @pytest.mark.asyncio
    async def test_gauge_height_only(self):
        """Station with gauge height but no discharge."""
        response = {
            "value": {
                "timeSeries": [
                    {
                        "variable": {"variableCode": [{"value": "00065"}]},
                        "values": [
                            {
                                "value": [
                                    {
                                        "value": "4.20",
                                        "dateTime": "2026-03-15T06:00:00.000",
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is not None
        assert result.discharge_cfs is None
        assert result.gauge_height_ft == 4.20

    @pytest.mark.asyncio
    async def test_empty_time_series_returns_none(self):
        response = {"value": {"timeSeries": []}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_time_series_key_returns_none(self):
        response = {"value": {}}
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_malformed_series_skipped(self):
        """Malformed series entries are skipped; valid ones still parsed."""
        response = {
            "value": {
                "timeSeries": [
                    {"bad": "data"},  # malformed — skipped
                    {
                        "variable": {"variableCode": [{"value": "00060"}]},
                        "values": [
                            {
                                "value": [
                                    {
                                        "value": "7000",
                                        "dateTime": "2026-03-15T06:00:00.000",
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is not None
        assert result.discharge_cfs == 7000.0

    @pytest.mark.asyncio
    async def test_empty_values_skipped(self):
        """Series with empty values list are skipped."""
        response = {
            "value": {
                "timeSeries": [
                    {
                        "variable": {"variableCode": [{"value": "00060"}]},
                        "values": [{"value": []}],
                    },
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = response
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get.return_value = mock_resp

        result = await fetch_usgs_gauge("14246900", client=mock_client)
        assert result is None

    @pytest.mark.asyncio
    async def test_creates_client_when_none(self):
        with patch("tidewise.sources.usgs.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.json.return_value = VALID_RESPONSE
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp
            mock_cls.return_value = mock_client

            result = await fetch_usgs_gauge("14246900")
            assert result is not None
            mock_client.aclose.assert_awaited_once()


class TestFetchUSGSGaugeSync:
    def test_sync_wrapper(self):
        with patch("tidewise.sources.usgs.asyncio.run") as mock_run:
            mock_run.return_value = None
            result = fetch_usgs_gauge_sync("14246900")
            assert result is None
            mock_run.assert_called_once()
