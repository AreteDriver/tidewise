"""USGS Water Services instantaneous values client."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from tidewise.models import USGSGaugeData

logger = logging.getLogger(__name__)

USGS_BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"

# USGS parameter codes
PARAM_DISCHARGE = "00060"  # Discharge, ft³/s
PARAM_GAUGE_HEIGHT = "00065"  # Gauge height, ft


async def fetch_usgs_gauge(
    gauge_id: str,
    client: httpx.AsyncClient | None = None,
) -> USGSGaugeData | None:
    """Fetch latest instantaneous values from USGS Water Services.

    Returns None on error (graceful degradation — gauge data is optional).
    """
    params = {
        "sites": gauge_id,
        "parameterCd": f"{PARAM_DISCHARGE},{PARAM_GAUGE_HEIGHT}",
        "format": "json",
        "siteStatus": "active",
        "period": "PT2H",
    }

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        resp = await client.get(USGS_BASE_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("USGS gauge fetch failed for %s: %s", gauge_id, e)
        return None
    finally:
        if should_close:
            await client.aclose()

    return _parse_usgs_response(data, gauge_id)


def fetch_usgs_gauge_sync(gauge_id: str) -> USGSGaugeData | None:
    """Synchronous wrapper for fetch_usgs_gauge."""
    return asyncio.run(fetch_usgs_gauge(gauge_id))


def _parse_usgs_response(data: dict, gauge_id: str) -> USGSGaugeData | None:
    """Parse USGS JSON response into USGSGaugeData."""
    try:
        time_series = data["value"]["timeSeries"]
    except (KeyError, TypeError):
        logger.debug("No timeSeries in USGS response for %s", gauge_id)
        return None

    if not time_series:
        return None

    discharge = None
    gauge_height = None
    latest_time = None

    for series in time_series:
        try:
            param_code = series["variable"]["variableCode"][0]["value"]
            values = series["values"][0]["value"]
            if not values:
                continue
            latest = values[-1]
            val = float(latest["value"])
            ts = datetime.strptime(latest["dateTime"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)

            if param_code == PARAM_DISCHARGE:
                discharge = val
                latest_time = ts
            elif param_code == PARAM_GAUGE_HEIGHT:
                gauge_height = val
                if latest_time is None:
                    latest_time = ts
        except (KeyError, ValueError, IndexError) as e:
            logger.debug("Error parsing USGS series for %s: %s", gauge_id, e)
            continue

    if latest_time is None:
        return None

    return USGSGaugeData(
        discharge_cfs=discharge,
        gauge_height_ft=gauge_height,
        timestamp=latest_time,
        gauge_id=gauge_id,
    )
