"""CLI entry point — Click command group."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from rich.console import Console

from tidewise.config import LocationConfig, StationConfig, TideWiseConfig, load_config

console = Console()


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to config file",
)
@click.option(
    "--profile",
    "profile_name",
    default=None,
    help="Use a named location profile from config",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None, profile_name: str | None) -> None:
    """TideWise — Personal fishing intelligence."""
    ctx.ensure_object(dict)
    cfg = load_config(config_path)

    if profile_name is not None:
        if profile_name not in cfg.profiles:
            available = ", ".join(sorted(cfg.profiles)) if cfg.profiles else "none defined"
            raise click.BadParameter(
                f"Profile '{profile_name}' not found. Available: {available}",
                param_hint="'--profile'",
            )
        profile = cfg.profiles[profile_name]
        if "location" in profile:
            loc = profile["location"]
            cfg.location = LocationConfig(
                name=loc.get("name", cfg.location.name),
                latitude=loc.get("latitude", cfg.location.latitude),
                longitude=loc.get("longitude", cfg.location.longitude),
                timezone=loc.get("timezone", cfg.location.timezone),
            )
        if "stations" in profile:
            st = profile["stations"]
            cfg.stations = StationConfig(
                tide=st.get("tide", cfg.stations.tide),
                water_temp=st.get("water_temp", cfg.stations.water_temp),
                usgs_gauge=st.get("usgs_gauge", cfg.stations.usgs_gauge),
            )

    ctx.obj["config"] = cfg


@main.command()
@click.pass_context
def today(ctx: click.Context) -> None:
    """Show today's fishing score and conditions."""
    cfg: TideWiseConfig = ctx.obj["config"]
    try:
        tide, weather, solunar, water_temp = _fetch_all_sources(cfg)
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.scoring.engine import calculate_score

    now = datetime.now(UTC)
    score = calculate_score(
        cfg.preferences.score_weights, tide, weather, solunar, now, water_temp=water_temp
    )

    from tidewise.display.terminal import render_today_summary

    render_today_summary(
        score, tide, weather, solunar, console, tz_name=cfg.location.timezone, water_temp=water_temp
    )

    if cfg.history.enabled:
        from tidewise.history import log_score as _log

        _log(score, cfg.location.name, cfg.stations.tide, now)


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
            datetime.now(UTC),
            days=days,
        )
    except Exception as e:
        console.print(f"[red]Error fetching tides: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.display.terminal import render_tide_forecast

    render_tide_forecast(tide, console, tz_name=cfg.location.timezone)


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
        tide, weather, solunar, water_temp = _fetch_all_sources(cfg, target)
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.scoring.engine import calculate_score

    result = calculate_score(
        cfg.preferences.score_weights, tide, weather, solunar, target, water_temp=water_temp
    )

    from tidewise.display.terminal import render_today_summary

    render_today_summary(
        result,
        tide,
        weather,
        solunar,
        console,
        tz_name=cfg.location.timezone,
        water_temp=water_temp,
    )

    if cfg.history.enabled:
        from tidewise.history import log_score as _log

        _log(result, cfg.location.name, cfg.stations.tide, target)


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
            tide, weather, solunar, water_temp = _fetch_all_sources(cfg, target)
            result = calculate_score(
                cfg.preferences.score_weights,
                tide,
                weather,
                solunar,
                target,
                water_temp=water_temp,
            )
            results.append((target, result))
        except Exception as e:
            console.print(f"[yellow]Skipping {target.strftime('%m/%d')}: {e}[/yellow]")

    if results:
        render_best_windows(results, console)
    else:
        console.print("[red]Could not fetch data for any dates.[/red]")


@main.command()
@click.option("--days", default=7, help="Number of days to forecast")
@click.pass_context
def week(ctx: click.Context, days: int) -> None:
    """Show multi-day fishing forecast."""
    cfg: TideWiseConfig = ctx.obj["config"]

    from tidewise.display.terminal import render_week_forecast
    from tidewise.scoring.engine import calculate_score

    results: list[tuple[datetime, object]] = []
    base = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)

    for i in range(days):
        target = base + timedelta(days=i)
        try:
            tide, weather, solunar, water_temp = _fetch_all_sources(cfg, target)
            result = calculate_score(
                cfg.preferences.score_weights,
                tide,
                weather,
                solunar,
                target,
                water_temp=water_temp,
            )
            results.append((target, result))
        except Exception as e:
            console.print(f"[yellow]Skipping {target.strftime('%m/%d')}: {e}[/yellow]")

    if results:
        render_week_forecast(results, console)
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
                tide, weather, solunar, water_temp = _fetch_all_sources(cfg)
                now = datetime.now(UTC)
                result = calculate_score(
                    cfg.preferences.score_weights,
                    tide,
                    weather,
                    solunar,
                    now,
                    water_temp=water_temp,
                )
                console.clear()
                console.print(f"[dim]Last updated: {now.strftime('%I:%M:%S %p')}[/dim]")
                tz = cfg.location.timezone
                render_today_summary(
                    result, tide, weather, solunar, console, tz_name=tz, water_temp=water_temp
                )
            except Exception as e:
                console.print(f"[red]Refresh error: {e}[/red]")

            import time

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard stopped.[/dim]")


@main.command()
@click.option("--force", is_flag=True, help="Send regardless of threshold/cooldown")
@click.pass_context
def notify(ctx: click.Context, force: bool) -> None:
    """One-shot notification check — cron/systemd-friendly."""
    cfg: TideWiseConfig = ctx.obj["config"]

    if not cfg.notifications.enabled and not force:
        console.print("[dim]Notifications disabled in config.[/dim]")
        return

    try:
        tide, weather, solunar, water_temp = _fetch_all_sources(cfg)
    except Exception as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        raise SystemExit(1) from None

    from tidewise.notifications import (
        format_score_alert,
        send_notification,
        should_notify,
        update_state,
    )
    from tidewise.scoring.engine import calculate_score

    now = datetime.now(UTC)
    score = calculate_score(
        cfg.preferences.score_weights, tide, weather, solunar, now, water_temp=water_temp
    )

    if not force and not should_notify(
        score.composite, cfg.notifications.alert_score, cfg.notifications.cooldown_minutes
    ):
        console.print(
            f"[dim]Score {score.composite:.1f}/10 "
            f"(threshold {cfg.notifications.alert_score}). No notification.[/dim]"
        )
        return

    title, body = format_score_alert(score, cfg.location.name, cfg.location.timezone)
    priority = "high" if score.composite >= 9.0 else "default"
    sent = asyncio.run(send_notification(cfg.notifications, title, body, priority=priority))

    if sent:
        update_state(score.composite)
        console.print(f"[green]Notification sent: {score.composite:.1f}/10[/green]")
    else:
        console.print("[yellow]Notification delivery failed.[/yellow]")


@main.command()
@click.option("--interval", default=300, help="Check interval in seconds")
@click.pass_context
def watch(ctx: click.Context, interval: int) -> None:
    """Continuous monitoring — sends alert when score crosses threshold."""
    cfg: TideWiseConfig = ctx.obj["config"]

    if not cfg.notifications.enabled:
        console.print("[dim]Notifications disabled in config.[/dim]")
        return

    from tidewise.notifications import (
        format_score_alert,
        send_notification,
        should_notify,
        update_state,
    )
    from tidewise.scoring.engine import calculate_score

    console.print(
        f"[bold]TideWise Watch[/bold] — "
        f"threshold {cfg.notifications.alert_score}, "
        f"interval {interval}s. Press Ctrl+C to stop.\n"
    )

    try:
        while True:
            try:
                tide, weather, solunar, water_temp = _fetch_all_sources(cfg)
                now = datetime.now(UTC)
                score = calculate_score(
                    cfg.preferences.score_weights,
                    tide,
                    weather,
                    solunar,
                    now,
                    water_temp=water_temp,
                )
                console.print(
                    f"[dim]{now.strftime('%H:%M:%S')} — Score: {score.composite:.1f}/10[/dim]"
                )

                if should_notify(
                    score.composite,
                    cfg.notifications.alert_score,
                    cfg.notifications.cooldown_minutes,
                ):
                    title, body = format_score_alert(
                        score, cfg.location.name, cfg.location.timezone
                    )
                    priority = "high" if score.composite >= 9.0 else "default"
                    sent = asyncio.run(
                        send_notification(cfg.notifications, title, body, priority=priority)
                    )
                    if sent:
                        update_state(score.composite)
                        console.print(f"[green]Alert sent: {score.composite:.1f}/10[/green]")
                    else:
                        console.print("[yellow]Alert delivery failed.[/yellow]")
            except Exception as e:
                console.print(f"[red]Watch error: {e}[/red]")

            import time

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


@main.command()
@click.option("--days", default=30, help="Number of days to show")
@click.option(
    "--export",
    "export_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Export history to CSV file",
)
@click.pass_context
def history(ctx: click.Context, days: int, export_path: Path | None) -> None:
    """Show historical fishing scores and trends."""
    cfg: TideWiseConfig = ctx.obj["config"]

    from tidewise.history import get_recent_scores, purge_old_records

    records = get_recent_scores(days=days, location=cfg.location.name)
    purge_old_records(retention_days=cfg.history.retention_days)

    if not records:
        console.print("[dim]No history yet. Run 'tidewise today' or 'tidewise score'.[/dim]")
        return

    if export_path is not None:
        from tidewise.history import export_csv

        export_csv(records, export_path)
        console.print(f"[green]Exported {len(records)} records to {export_path}[/green]")
        return

    from tidewise.display.terminal import render_score_history

    render_score_history(records, console)


def _fetch_all_sources(cfg: TideWiseConfig, target: datetime | None = None) -> tuple:
    """Fetch tide + weather + water temp concurrently, solunar synchronously.

    Returns (TideData, WeatherData, SolunarData, WaterTempData | None).
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
        from tidewise.sources.water_temp import fetch_water_temp
        from tidewise.sources.weather import fetch_weather

        async with httpx.AsyncClient() as client:
            tide_task = fetch_tides(cfg.stations.tide, target, now=target, client=client)
            weather_task = fetch_weather(
                cfg.location.latitude,
                cfg.location.longitude,
                target,
                client=client,
            )
            water_temp_task = fetch_water_temp(cfg.stations.water_temp, client=client)
            return await asyncio.gather(tide_task, weather_task, water_temp_task)

    tide, weather, water_temp = asyncio.run(_fetch_async())

    return tide, weather, solunar, water_temp
