"""Rich terminal dashboard for TideWise."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from tidewise.models import (
    FishingScore,
    MoonPhase,
    PressureTrend,
    SolunarData,
    TideData,
    TideDirection,
    WeatherData,
)


def render_today_summary(
    score: FishingScore,
    tide: TideData,
    weather: WeatherData,
    solunar: SolunarData,
    console: Console | None = None,
    tz_name: str | None = None,
) -> None:
    """Render concise daily summary to terminal."""
    if console is None:
        console = Console()

    console.print()
    console.print(_build_score_panel(score))
    console.print()
    console.print(_build_tide_panel(tide, tz_name=tz_name))
    console.print(_build_weather_panel(weather))
    console.print(_build_solunar_panel(solunar))
    console.print()
    console.print(_build_suggestions_panel(score))
    console.print()


def render_tide_forecast(
    tide: TideData, console: Console | None = None, tz_name: str | None = None
) -> None:
    """Render tide predictions as a table."""
    if console is None:
        console = Console()

    table = Table(title=f"Tide Predictions — Station {tide.station_id}", show_lines=True)
    table.add_column("Time", style="cyan")
    table.add_column("Height (ft)", justify="right")
    table.add_column("Type", style="bold")

    for pred in tide.predictions:
        type_style = "blue" if pred.type.value == "high" else "green"
        display_time = _to_local(pred.time, tz_name)
        table.add_row(
            display_time.strftime("%a %m/%d %I:%M %p"),
            f"{pred.height_ft:.1f}",
            Text(pred.type.value.upper(), style=type_style),
        )

    console.print()
    console.print(table)
    console.print()


def render_best_windows(
    scores: list[tuple[datetime, FishingScore]],
    console: Console | None = None,
) -> None:
    """Render ranked best fishing windows."""
    if console is None:
        console = Console()

    table = Table(title="Best Fishing Windows", show_lines=True)
    table.add_column("Date", style="cyan")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Best Window")
    table.add_column("Reason")

    sorted_scores = sorted(scores, key=lambda x: x[1].composite, reverse=True)
    for date, score in sorted_scores:
        color = _score_color(score.composite)
        window = ""
        if score.best_window_start and score.best_window_end:
            window = (
                f"{score.best_window_start.strftime('%H:%M')} - "
                f"{score.best_window_end.strftime('%H:%M')}"
            )
        elif score.best_window_start:
            window = f"From {score.best_window_start.strftime('%H:%M')}"

        table.add_row(
            date.strftime("%a %m/%d"),
            Text(f"{score.composite:.1f}", style=color),
            window,
            score.best_window_reason,
        )

    console.print()
    console.print(table)
    console.print()


def render_score_history(
    records: list[dict],
    console: Console | None = None,
) -> None:
    """Render historical score records as a table with trend arrows."""
    if console is None:
        console = Console()

    table = Table(title="Score History", show_lines=True)
    table.add_column("Date", style="cyan")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Trend")
    table.add_column("Best Window")
    table.add_column("Reason")

    for i, rec in enumerate(records):
        color = _score_color(rec["composite"])
        score_val = rec["composite"]

        # Trend arrow: compare to next (older) record
        if i + 1 < len(records):
            prev = records[i + 1]["composite"]
            if score_val > prev + 0.5:
                trend = Text("\u2191", style="green")
            elif score_val < prev - 0.5:
                trend = Text("\u2193", style="red")
            else:
                trend = Text("\u2192", style="dim")
        else:
            trend = Text("-", style="dim")

        window = ""
        if rec.get("best_window_start") and rec.get("best_window_end"):
            try:
                start = datetime.fromisoformat(rec["best_window_start"])
                end = datetime.fromisoformat(rec["best_window_end"])
                window = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
            except (ValueError, TypeError):
                pass

        ts = datetime.fromisoformat(rec["timestamp"])
        table.add_row(
            ts.strftime("%a %m/%d %I:%M %p"),
            Text(f"{score_val:.1f}", style=color),
            trend,
            window,
            rec.get("best_window_reason", ""),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]{len(records)} records shown[/dim]")
    console.print()


def _build_score_panel(score: FishingScore) -> Panel:
    """Build the main score panel."""
    color = _score_color(score.composite)

    # Score display
    score_text = Text()
    score_text.append(f"  {score.composite:.1f}", style=f"bold {color}")
    score_text.append(" / 10\n\n")

    # Factor breakdown
    for factor in score.factors:
        bar_len = int(factor.score * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        score_text.append(f"  {factor.name:<14s} ", style="dim")
        score_text.append(f"{bar} ", style=color)
        score_text.append(f"{factor.score:.2f}", style="bold")
        score_text.append(f"  {factor.detail}\n", style="dim")

    # Best window
    if score.best_window_start:
        score_text.append("\n  Best Window: ", style="bold")
        if score.best_window_end:
            score_text.append(
                f"{score.best_window_start.strftime('%H:%M')} - "
                f"{score.best_window_end.strftime('%H:%M')}"
            )
        score_text.append(f" — {score.best_window_reason}\n")

    return Panel(score_text, title="[bold]Fishing Score[/bold]", border_style=color)


def _build_tide_panel(tide: TideData, tz_name: str | None = None) -> Panel:
    """Build the tide info panel."""
    text = Text()
    text.append("  Direction: ", style="dim")
    text.append(f"{_tide_direction_display(tide.current_direction)}\n", style="bold")

    if tide.next_event:
        hours = tide.minutes_until_next // 60
        mins = tide.minutes_until_next % 60
        display_time = _to_local(tide.next_event.time, tz_name)
        text.append(f"  Next {tide.next_event.type.value.title()}: ", style="dim")
        text.append(
            f"{display_time.strftime('%I:%M %p')} "
            f"({tide.next_event.height_ft:.1f} ft) — "
            f"{hours}h {mins}m\n"
        )

    return Panel(text, title="[bold]Tides[/bold]", border_style="blue")


def _build_weather_panel(weather: WeatherData) -> Panel:
    """Build the weather info panel."""
    text = Text()
    text.append("  Temp: ", style="dim")
    text.append(f"{weather.temperature_f:.0f}°F\n")
    text.append("  Pressure: ", style="dim")
    text.append(
        f"{weather.pressure_inhg:.2f} inHg {_pressure_trend_arrow(weather.pressure_trend)}\n"
    )
    text.append("  Wind: ", style="dim")
    text.append(
        f"{weather.wind_speed_mph:.0f} mph {weather.wind_direction} "
        f"(gusts {weather.wind_gust_mph:.0f} mph)\n"
    )
    text.append("  Cloud Cover: ", style="dim")
    text.append(f"{weather.cloud_cover_pct:.0f}%\n")
    text.append("  Precipitation: ", style="dim")
    text.append(f"{weather.precipitation_mm:.1f} mm\n")

    return Panel(text, title="[bold]Weather[/bold]", border_style="yellow")


def _build_solunar_panel(solunar: SolunarData) -> Panel:
    """Build the solunar info panel."""
    text = Text()
    text.append("  Moon: ", style="dim")
    text.append(
        f"{_moon_phase_display(solunar.moon_phase)} "
        f"({solunar.moon_illumination * 100:.0f}% illumination)\n"
    )

    if solunar.major_periods:
        text.append("  Major: ", style="dim")
        parts = []
        for p in solunar.major_periods:
            parts.append(f"{p.start.strftime('%H:%M')}-{p.end.strftime('%H:%M')}")
        text.append(", ".join(parts) + "\n")

    if solunar.minor_periods:
        text.append("  Minor: ", style="dim")
        parts = []
        for p in solunar.minor_periods:
            parts.append(f"{p.start.strftime('%H:%M')}-{p.end.strftime('%H:%M')}")
        text.append(", ".join(parts) + "\n")

    if solunar.sunrise:
        text.append("  Sunrise: ", style="dim")
        text.append(f"{solunar.sunrise.strftime('%I:%M %p')}  ")
    if solunar.sunset:
        text.append("Sunset: ", style="dim")
        text.append(f"{solunar.sunset.strftime('%I:%M %p')}\n")

    return Panel(text, title="[bold]Solunar[/bold]", border_style="magenta")


def _build_suggestions_panel(score: FishingScore) -> Panel:
    """Build the suggestions panel."""
    text = Text()
    if score.suggestions:
        for i, s in enumerate(score.suggestions, 1):
            text.append(f"  {i}. {s}\n")
    else:
        text.append("  No specific suggestions for current conditions.\n", style="dim")

    return Panel(text, title="[bold]Suggestions[/bold]", border_style="green")


def _to_local(dt: datetime, tz_name: str | None) -> datetime:
    """Convert a datetime to local timezone if tz_name provided."""
    if tz_name and dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo(tz_name))
    return dt


def _score_color(score: float) -> str:
    """Return color name based on score value."""
    if score >= 8:
        return "green"
    elif score >= 6:
        return "yellow"
    elif score >= 4:
        return "dark_orange"
    else:
        return "red"


def _pressure_trend_arrow(trend: PressureTrend) -> str:
    """Return arrow character for pressure trend."""
    arrows = {
        PressureTrend.RAPIDLY_FALLING: "↓↓",
        PressureTrend.FALLING: "↓",
        PressureTrend.STEADY: "→",
        PressureTrend.RISING: "↑",
        PressureTrend.RAPIDLY_RISING: "↑↑",
    }
    return arrows.get(trend, "→")


def _tide_direction_display(direction: TideDirection) -> str:
    """Display string for tide direction."""
    display = {
        TideDirection.INCOMING: "↗ Incoming",
        TideDirection.OUTGOING: "↘ Outgoing",
        TideDirection.SLACK: "↔ Slack",
    }
    return display.get(direction, str(direction))


def _moon_phase_display(phase: MoonPhase) -> str:
    """Human-readable moon phase display."""
    display = {
        MoonPhase.NEW_MOON: "🌑 New Moon",
        MoonPhase.WAXING_CRESCENT: "🌒 Waxing Crescent",
        MoonPhase.FIRST_QUARTER: "🌓 First Quarter",
        MoonPhase.WAXING_GIBBOUS: "🌔 Waxing Gibbous",
        MoonPhase.FULL_MOON: "🌕 Full Moon",
        MoonPhase.WANING_GIBBOUS: "🌖 Waning Gibbous",
        MoonPhase.LAST_QUARTER: "🌗 Last Quarter",
        MoonPhase.WANING_CRESCENT: "🌘 Waning Crescent",
    }
    return display.get(phase, str(phase))
