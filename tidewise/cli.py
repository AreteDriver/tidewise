"""CLI entry point — Click command group."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console

from tidewise.config import TideWiseConfig, load_config

console = Console()


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to config file",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """TideWise — Personal fishing intelligence."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)


@main.command()
@click.pass_context
def today(ctx: click.Context) -> None:
    """Show today's fishing score and conditions."""
    cfg: TideWiseConfig = ctx.obj["config"]
    try:
        tide, weather, solunar = _fetch_all_sources(cfg)
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.scoring.engine import calculate_score

    now = datetime.now(UTC)
    score = calculate_score(cfg.preferences.score_weights, tide, weather, solunar, now)

    from tidewise.display.terminal import render_today_summary

    render_today_summary(score, tide, weather, solunar, console)


@main.command()
@click.option("--days", default=3, help="Number of days to show")
@click.pass_context
def tides(ctx: click.Context, days: int) -> None:
    """Show tide predictions."""
    cfg: TideWiseConfig = ctx.obj["config"]
    try:
        from tidewise.sources.tides import fetch_tides_sync

        tide = fetch_tides_sync(
            cfg.stations.tide,
            datetime.now(),
            days=days,
        )
    except Exception as e:
        console.print(f"[red]Error fetching tides: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.display.terminal import render_tide_forecast

    render_tide_forecast(tide, console)


@main.command()
@click.option("--date", "date_str", default=None, help="Date (YYYY-MM-DD)")
@click.pass_context
def score(ctx: click.Context, date_str: str | None) -> None:
    """Calculate fishing score for a date."""
    cfg: TideWiseConfig = ctx.obj["config"]

    if date_str:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            raise SystemExit(1) from None
    else:
        target = datetime.now(UTC)

    try:
        tide, weather, solunar = _fetch_all_sources(cfg, target)
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.scoring.engine import calculate_score

    result = calculate_score(cfg.preferences.score_weights, tide, weather, solunar, target)

    from tidewise.display.terminal import render_today_summary

    render_today_summary(result, tide, weather, solunar, console)


@main.command()
@click.option("--days", default=7, help="Number of days to check")
@click.pass_context
def best(ctx: click.Context, days: int) -> None:
    """Find best fishing windows over a date range."""
    cfg: TideWiseConfig = ctx.obj["config"]

    from tidewise.display.terminal import render_best_windows
    from tidewise.scoring.engine import calculate_score

    results: list[tuple[datetime, object]] = []
    base = datetime.now(UTC).replace(hour=16, minute=0, second=0, microsecond=0)

    for i in range(days):
        target = base + timedelta(days=i)
        try:
            tide, weather, solunar = _fetch_all_sources(cfg, target)
            result = calculate_score(cfg.preferences.score_weights, tide, weather, solunar, target)
            results.append((target, result))
        except Exception as e:
            console.print(f"[yellow]Skipping {target.strftime('%m/%d')}: {e}[/yellow]")

    if results:
        render_best_windows(results, console)
    else:
        console.print("[red]Could not fetch data for any dates.[/red]")


@main.command()
@click.option("--interval", default=300, help="Refresh interval in seconds")
@click.pass_context
def dashboard(ctx: click.Context, interval: int) -> None:
    """Live fishing dashboard with auto-refresh."""
    cfg: TideWiseConfig = ctx.obj["config"]

    from tidewise.display.terminal import render_today_summary
    from tidewise.scoring.engine import calculate_score

    console.print("[bold]TideWise Dashboard[/bold] — Press Ctrl+C to exit\n")

    try:
        while True:
            try:
                tide, weather, solunar = _fetch_all_sources(cfg)
                now = datetime.now(UTC)
                result = calculate_score(cfg.preferences.score_weights, tide, weather, solunar, now)
                console.clear()
                console.print(f"[dim]Last updated: {now.strftime('%I:%M:%S %p')}[/dim]")
                render_today_summary(result, tide, weather, solunar, console)
            except Exception as e:
                console.print(f"[red]Refresh error: {e}[/red]")

            import time

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")


def _fetch_all_sources(cfg: TideWiseConfig, target: datetime | None = None) -> tuple:
    """Fetch tide + weather concurrently, solunar synchronously.

    Returns (TideData, WeatherData, SolunarData).
    """
    if target is None:
        target = datetime.now(UTC)

    from tidewise.sources.solunar import get_solunar_data

    solunar = get_solunar_data(
        cfg.location.latitude,
        cfg.location.longitude,
        target,
        cfg.location.timezone,
    )

    async def _fetch_async():
        import httpx

        from tidewise.sources.tides import fetch_tides
        from tidewise.sources.weather import fetch_weather

        async with httpx.AsyncClient() as client:
            tide_task = fetch_tides(cfg.stations.tide, target, now=target, client=client)
            weather_task = fetch_weather(
                cfg.location.latitude,
                cfg.location.longitude,
                target,
                client=client,
            )
            return await asyncio.gather(tide_task, weather_task)

    tide, weather = asyncio.run(_fetch_async())

    return tide, weather, solunar
