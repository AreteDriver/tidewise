"""Configuration loading — YAML config with sensible defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LocationConfig:
    name: str = "Columbia River - Astoria"
    latitude: float = 46.1879
    longitude: float = -123.8313
    timezone: str = "America/Los_Angeles"


@dataclass
class StationConfig:
    tide: str = "9439040"
    water_temp: str = "9439040"
    usgs_gauge: str | None = None


@dataclass
class ScoreWeights:
    solunar: float = 0.25
    tide: float = 0.25
    pressure: float = 0.20
    wind: float = 0.15
    cloud: float = 0.10
    precipitation: float = 0.05


@dataclass
class PreferencesConfig:
    units: str = "imperial"
    time_format: str = "12h"
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)


@dataclass
class NotificationConfig:
    enabled: bool = False
    method: str = "ntfy"  # ntfy | desktop | both | none
    ntfy_url: str = "https://ntfy.sh"
    ntfy_topic: str = "tidewise-fishing"
    alert_score: float = 8.0
    cooldown_minutes: int = 60


@dataclass
class HistoryConfig:
    enabled: bool = True
    retention_days: int = 365


@dataclass
class TideWiseConfig:
    location: LocationConfig = field(default_factory=LocationConfig)
    stations: StationConfig = field(default_factory=StationConfig)
    preferences: PreferencesConfig = field(default_factory=PreferencesConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)
    profiles: dict[str, dict] = field(default_factory=dict)


_CONFIG_SEARCH_PATHS = [
    Path("config/tidewise.yaml"),
    Path.home() / ".config" / "tidewise" / "tidewise.yaml",
    Path("/etc/tidewise/tidewise.yaml"),
]


def load_config(path: Path | None = None) -> TideWiseConfig:
    """Load config from YAML file, falling back to defaults.

    Search order: explicit path > ./config/tidewise.yaml > ~/.config/tidewise/ > /etc/tidewise/
    """
    if path is not None:
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        return _parse_config(config_path)

    for candidate in _CONFIG_SEARCH_PATHS:
        if candidate.exists():
            return _parse_config(candidate)

    return TideWiseConfig()


def _parse_config(path: Path) -> TideWiseConfig:
    """Parse a YAML config file into TideWiseConfig."""
    raw = yaml.safe_load(path.read_text()) or {}

    location_raw = raw.get("location", {})
    location = LocationConfig(
        name=location_raw.get("name", LocationConfig.name),
        latitude=location_raw.get("latitude", LocationConfig.latitude),
        longitude=location_raw.get("longitude", LocationConfig.longitude),
        timezone=location_raw.get("timezone", LocationConfig.timezone),
    )

    stations_raw = raw.get("stations", {})
    stations = StationConfig(
        tide=stations_raw.get("tide", StationConfig.tide),
        water_temp=stations_raw.get("water_temp", StationConfig.water_temp),
        usgs_gauge=stations_raw.get("usgs_gauge"),
    )

    prefs_raw = raw.get("preferences", {})
    weights_raw = prefs_raw.get("score_weights", {})
    weights = ScoreWeights(
        solunar=weights_raw.get("solunar", ScoreWeights.solunar),
        tide=weights_raw.get("tide", ScoreWeights.tide),
        pressure=weights_raw.get("pressure", ScoreWeights.pressure),
        wind=weights_raw.get("wind", ScoreWeights.wind),
        cloud=weights_raw.get("cloud", ScoreWeights.cloud),
        precipitation=weights_raw.get("precipitation", ScoreWeights.precipitation),
    )
    preferences = PreferencesConfig(
        units=prefs_raw.get("units", PreferencesConfig.units),
        time_format=prefs_raw.get("time_format", PreferencesConfig.time_format),
        score_weights=weights,
    )

    notif_raw = raw.get("notifications", {})
    notifications = NotificationConfig(
        enabled=notif_raw.get("enabled", NotificationConfig.enabled),
        method=notif_raw.get("method", NotificationConfig.method),
        ntfy_url=notif_raw.get("ntfy_url", NotificationConfig.ntfy_url),
        ntfy_topic=notif_raw.get("ntfy_topic", NotificationConfig.ntfy_topic),
        alert_score=float(notif_raw.get("alert_score", NotificationConfig.alert_score)),
        cooldown_minutes=int(
            notif_raw.get("cooldown_minutes", NotificationConfig.cooldown_minutes)
        ),
    )

    history_raw = raw.get("history", {})
    history = HistoryConfig(
        enabled=history_raw.get("enabled", HistoryConfig.enabled),
        retention_days=int(history_raw.get("retention_days", HistoryConfig.retention_days)),
    )

    profiles = raw.get("profiles", {})

    return TideWiseConfig(
        location=location,
        stations=stations,
        preferences=preferences,
        notifications=notifications,
        history=history,
        profiles=profiles,
    )
