# TideWise

[![CI](https://github.com/AreteDriver/tidewise/actions/workflows/ci.yml/badge.svg)](https://github.com/AreteDriver/tidewise/actions/workflows/ci.yml)

Local-first fishing intelligence — tides, weather, solunar, water temperature, and river gauge data combined into a single daily score (1-10).

## Features

- **Composite scoring** — 7 weighted factors (solunar, tide, pressure, wind, cloud, precipitation, water temp) produce a 1-10 daily score
- **Best window finder** — identifies optimal fishing windows by overlapping solunar major periods with incoming tides
- **Weekly forecast** — multi-day fishing forecast with daily scores, trends, and top factors
- **Rich terminal dashboard** — color-coded panels for score, tides, weather, water temp, river gauge, solunar, and suggestions
- **Metric & imperial units** — configurable display units for temperature, pressure, wind, tide heights, and river data
- **USGS river gauges** — optional discharge (cfs) and gauge height from USGS Water Services
- **NOAA water temperature** — real-time water temp from NOAA observation stations
- **Notifications** — ntfy.sh push notifications and desktop alerts (`notify-send`) with cooldown and threshold control
- **Historical tracking** — auto-log scores to SQLite, view trends, export to CSV
- **Location profiles** — switch between fishing spots with `--profile`
- **Fully offline solunar** — Skyfield ephemeris for moon phase, major/minor periods, sunrise/sunset (no API needed)
- **NOAA tides** — real-time tide predictions from NOAA Tides & Currents API
- **Open-Meteo weather** — pressure trends, wind, cloud cover, precipitation (free, no API key)

## Install

```bash
git clone https://github.com/AreteDriver/tidewise.git
cd tidewise
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

```bash
# Today's fishing score and conditions
tidewise today

# Tide predictions (default 3 days)
tidewise tides --days 5

# Score for a specific date
tidewise score --date 2026-03-15

# Best fishing windows over a week
tidewise best --days 7

# Multi-day fishing forecast
tidewise week --days 7

# Live dashboard with auto-refresh
tidewise dashboard --interval 300

# One-shot notification (cron-friendly)
tidewise notify

# Continuous monitoring with alerts
tidewise watch --interval 300

# View score history and trends
tidewise history --days 30

# Export history to CSV
tidewise history --export scores.csv

# Use a named location profile
tidewise --profile newport today
```

## Configuration

Copy the example and edit for your location:

```bash
mkdir -p ~/.config/tidewise
cp config/tidewise.yaml.example ~/.config/tidewise/tidewise.yaml
```

```yaml
location:
  name: "Columbia River - Astoria"
  latitude: 46.1879
  longitude: -123.8313
  timezone: "America/Los_Angeles"

stations:
  tide: "9439040"           # NOAA station ID
  water_temp: "9439040"     # NOAA water temp station (often same as tide)
  usgs_gauge: "14246900"    # Optional USGS gauge for river discharge/height

preferences:
  units: imperial            # imperial | metric
  time_format: 12h
  score_weights:
    solunar: 0.25
    tide: 0.25
    pressure: 0.20
    wind: 0.15
    cloud: 0.10
    precipitation: 0.05
    water_temp: 0.10         # weights are normalized — don't need to sum to 1.0

notifications:
  enabled: true
  method: ntfy               # ntfy | desktop | both | none
  ntfy_url: "https://ntfy.sh"
  ntfy_topic: "tidewise-fishing"
  alert_score: 8.0
  cooldown_minutes: 60

history:
  enabled: true
  retention_days: 365

# Named location profiles — switch with --profile
profiles:
  newport:
    location:
      name: "Yaquina Bay - Newport"
      latitude: 44.6253
      longitude: -124.0535
    stations:
      tide: "9435380"
      water_temp: "9435380"
```

Find your NOAA station ID at [tidesandcurrents.noaa.gov](https://tidesandcurrents.noaa.gov/stations.html). Find USGS gauges at [waterdata.usgs.gov](https://waterdata.usgs.gov/nwis).

Config search order: `--config` flag > `./config/tidewise.yaml` > `~/.config/tidewise/tidewise.yaml` > `/etc/tidewise/tidewise.yaml` > defaults.

## Data Sources

| Source | Data | API Key |
|--------|------|---------|
| NOAA Tides & Currents | Tide predictions, water temperature | None |
| Open-Meteo | Temperature, pressure, wind, cloud, precipitation | None |
| USGS Water Services | River discharge, gauge height | None |
| Skyfield (local) | Moon phase, solunar periods, sunrise/sunset | None |

## Notifications

TideWise supports push notifications via [ntfy.sh](https://ntfy.sh) (free, no account needed) and desktop notifications via `notify-send`.

**Cron example** — check every morning at 5 AM:

```cron
0 5 * * * /path/to/.venv/bin/tidewise notify
```

**Phone alerts** — install the [ntfy app](https://ntfy.sh), subscribe to your topic, and receive push notifications when conditions are favorable.

## Tests

```bash
pytest -q --no-header
ruff check . && ruff format --check .
```

373 tests, 97% coverage.

## License

MIT
