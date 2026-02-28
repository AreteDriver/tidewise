# CLAUDE.md — tidewise

## Project Overview

Local-first fishing intelligence — tides, weather, solunar scoring

## Current State

- **Version**: 0.4.0
- **Language**: Python
- **Files**: 45 across 1 languages
- **Lines**: 7,400

## Architecture

```
tidewise/
├── .github/
│   └── workflows/
├── config/
├── tests/
├── tidewise/
│   ├── display/
│   ├── scoring/
│   └── sources/
├── .gitignore
├── .gitleaks.toml
├── README.md
├── pyproject.toml
```

## Tech Stack

- **Language**: Python
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Test Frameworks**: pytest
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: partial
- **Docstrings**: google style
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 78 characters
- **Error Handling**: Custom exception classes present

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check src/ tests/
# format
ruff format src/ tests/
# coverage
pytest --cov=src/ tests/
# tidewise
tidewise.cli:main
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module

## Dependencies

### Core
- httpx
- skyfield
- rich
- pyyaml
- click

### Dev
- pytest
- pytest-cov
- pytest-asyncio
- ruff
- respx

## Domain Context

### Key Models/Classes
- `FactorScore`
- `FishingScore`
- `HistoryConfig`
- `LocationConfig`
- `MoonPhase`
- `NotificationConfig`
- `PreferencesConfig`
- `PressureTrend`
- `ScoreWeights`
- `SolunarData`
- `SolunarPeriod`
- `SolunarPeriodType`
- `StationConfig`
- `TestAutoLogging`
- `TestBestCommand`

### Domain Terms
- AM
- CI
- CSV
- Columbia River
- Configuration Copy
- Data Sources
- ID
- MIT
- NOAA
- Requires Python

### Enums/Constants
- `FALLING`
- `FIRST_QUARTER`
- `FULL_MOON`
- `HIGH`
- `INCOMING`
- `LAST_QUARTER`
- `LOW`
- `MAJOR`
- `MINOR`
- `NEW_MOON`

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
