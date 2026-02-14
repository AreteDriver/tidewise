"""NOAA water temperature observation client."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from tidewise.models import WaterTempData

logger = logging.getLogger(__name__)

NOAA_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


async def fetch_water_temp(
    station_id: str,
    client: httpx.AsyncClient | None = None,
) -> WaterTempData | None:
    """Fetch latest water temperature from NOAA for a station.

    Returns None if the station has no temp sensor or on any error
    (graceful degradation — water temp is optional).
    """
    params = {
        "station": station_id,
        "date": "latest",
        "product": "water_temperature",
        "units": "english",
        "time_zone": "gmt",
        "format": "json",
        "application": "tidewise",
    }

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        resp = await client.get(NOAA_BASE_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.debug("Water temp fetch failed for station %s: %s", station_id, e)
        return None
    finally:
        if should_close:
            await client.aclose()

    if "error" in data:
        logger.debug("NOAA water temp error for %s: %s", station_id, data["error"])
        return None

    if "data" not in data or not data["data"]:
        logger.debug("No water temp data for station %s", station_id)
        return None

    try:
        entry = data["data"][0]
        temp_f = float(entry["v"])
        timestamp = datetime.strptime(entry["t"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        return WaterTempData(
            temperature_f=temp_f,
            timestamp=timestamp,
            station_id=station_id,
        )
    except (KeyError, ValueError, IndexError) as e:
        logger.debug("Malformed water temp response for %s: %s", station_id, e)
        return None


def fetch_water_temp_sync(station_id: str) -> WaterTempData | None:
    """Synchronous wrapper for fetch_water_temp."""
    return asyncio.run(fetch_water_temp(station_id))
