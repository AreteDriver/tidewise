"""NOAA Tides & Currents API client."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx

from tidewise.models import TideData, TideDirection, TidePrediction, TideType

NOAA_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

# Minutes around high/low where tide is considered slack
SLACK_WINDOW_MINUTES = 30


class TideAPIError(Exception):
    """Raised when the NOAA API returns an error or malformed response."""


async def fetch_tides(
    station_id: str,
    date: datetime,
    days: int = 1,
    now: datetime | None = None,
    client: httpx.AsyncClient | None = None,
) -> TideData:
    """Fetch tide predictions from NOAA for a station and date range.

    Args:
        station_id: NOAA tide station ID
        date: Start date for predictions
        days: Number of days to fetch
        now: Current time for direction calculation (defaults to utcnow)
        client: Optional httpx client for connection reuse
    """
    begin = date.strftime("%Y%m%d")
    end = (date + timedelta(days=days)).strftime("%Y%m%d")

    params = {
        "station": station_id,
        "begin_date": begin,
        "end_date": end,
        "product": "predictions",
        "datum": "MLLW",
        "interval": "hilo",
        "time_zone": "lst_ldt",
        "units": "english",
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
    except httpx.HTTPError as e:
        raise TideAPIError(f"NOAA API request failed: {e}") from e
    finally:
        if should_close:
            await client.aclose()

    if "error" in data:
        raise TideAPIError(f"NOAA API error: {data['error'].get('message', data['error'])}")

    if "predictions" not in data:
        raise TideAPIError("NOAA API response missing 'predictions' key")

    predictions = _parse_predictions(data["predictions"])

    if now is None:
        now = datetime.now()

    direction = _determine_tide_direction(predictions, now)
    next_event, minutes_until = _find_next_event(predictions, now)

    return TideData(
        predictions=predictions,
        current_direction=direction,
        next_event=next_event,
        minutes_until_next=minutes_until,
        station_id=station_id,
    )


def fetch_tides_sync(
    station_id: str,
    date: datetime,
    days: int = 1,
    now: datetime | None = None,
) -> TideData:
    """Synchronous wrapper for fetch_tides."""
    return asyncio.run(fetch_tides(station_id, date, days=days, now=now))


def _parse_predictions(raw: list[dict]) -> list[TidePrediction]:
    """Parse NOAA JSON predictions into TidePrediction objects.

    NOAA format: {"t": "2026-03-15 09:45", "v": "8.100", "type": "H"}
    """
    predictions = []
    for entry in raw:
        try:
            time = datetime.strptime(entry["t"], "%Y-%m-%d %H:%M")
            height = float(entry["v"])
            tide_type = TideType.HIGH if entry["type"] == "H" else TideType.LOW
            predictions.append(TidePrediction(time=time, height_ft=height, type=tide_type))
        except (KeyError, ValueError) as e:
            raise TideAPIError(f"Malformed tide prediction: {entry} — {e}") from e

    return predictions


def _determine_tide_direction(predictions: list[TidePrediction], now: datetime) -> TideDirection:
    """Determine if the tide is incoming, outgoing, or slack.

    Bracket `now` between the two nearest H/L events.
    Within SLACK_WINDOW_MINUTES of an event = slack.
    Between low→high = incoming, high→low = outgoing.
    """
    if not predictions:
        return TideDirection.SLACK

    # Check if we're within slack window of any event
    for pred in predictions:
        minutes_diff = abs((pred.time - now).total_seconds() / 60)
        if minutes_diff <= SLACK_WINDOW_MINUTES:
            return TideDirection.SLACK

    # Find the predictions bracketing now
    prev_event = None
    next_event = None
    for pred in predictions:
        if pred.time <= now:
            prev_event = pred
        elif next_event is None:
            next_event = pred
            break

    if prev_event is None or next_event is None:
        # Can't determine — we're outside the prediction range
        if predictions:
            # Use first prediction as reference
            if predictions[0].type == TideType.HIGH:
                return TideDirection.INCOMING
            return TideDirection.OUTGOING
        return TideDirection.SLACK

    # Low → High = incoming, High → Low = outgoing
    if prev_event.type == TideType.LOW and next_event.type == TideType.HIGH:
        return TideDirection.INCOMING
    elif prev_event.type == TideType.HIGH and next_event.type == TideType.LOW:
        return TideDirection.OUTGOING
    else:
        return TideDirection.SLACK


def _find_next_event(
    predictions: list[TidePrediction], now: datetime
) -> tuple[TidePrediction | None, int]:
    """Find the next future tide event and minutes until it occurs."""
    for pred in predictions:
        if pred.time > now:
            minutes = int((pred.time - now).total_seconds() / 60)
            return pred, minutes

    return None, 0
