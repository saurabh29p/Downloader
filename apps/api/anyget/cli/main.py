"""The `anyget` command line tool. Runs the engine in-process; no server needed."""

import asyncio
import contextlib
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table

from anyget import __version__
from anyget.core.jobs import ACTIVE_STATES, FINISHED_STATES, JobState
from anyget.core.net import BlockedURLError
from anyget.core.router import normalize
from anyget.core.services import Services
from anyget.core.settings import get_settings
from anyget.handlers.base import HandlerError

app = typer.Typer(help="AnyGet: paste any public link, get the file.", no_args_is_help=True)
console = Console()


@app.command()
def version() -> None:
    """Show the AnyGet version."""
    console.print(f"anyget {__version__}")


@app.command()
def health(
    url: Annotated[str | None, typer.Option(help="API base URL (default: from settings)")] = None,
) -> None:
    """Check that the AnyGet API is running."""
    settings = get_settings()
    base = url or f"http://{settings.host}:{settings.port}"
    try:
        response = httpx.get(f"{base}/api/health", timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        console.print(f"[red]API not reachable at {base}:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]API ok[/green] at {base}")


def _read_urls(urls: list[str], input_file: Path | None) -> list[str]:
    collected = list(urls)
    if input_file is not None:
        for line in input_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                collected.append(line)
    return collected


async def _get(urls: list[str]) -> int:
    services = Services.build(get_settings())
    await services.start(recover=False)  # leave other processes' jobs alone
    events = services.bus.subscribe()
    failures = 0
    job_ids: list[str] = []
    try:
        for raw in urls:
            try:
                url = normalize(raw)
                await services.net.check(url)
            except BlockedURLError as exc:
                console.print(f"[red]✗[/red] {raw}: {exc}")
                failures += 1
                continue
            existing = services.store.find_resumable(url)
            if existing is not None:
                console.print(f"[cyan]↻[/cyan] resuming {url}")
                if existing.state == JobState.queued:
                    services.queue.schedule(existing.id)
                else:
                    services.queue.resume(existing.id)
                job_ids.append(existing.id)
            else:
                job_ids.append(services.queue.submit(url).id)

        if not job_ids:
            return 1
        with Progress(
            TextColumn("[bold]{task.description}", justify="left"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            bars: dict[str, TaskID] = {
                job_id: progress.add_task("starting…", total=None) for job_id in job_ids
            }
            remaining = set(job_ids)
            try:
                async for event in events:
                    job = event["job"]
                    job_id = job.get("id")
                    if job_id not in bars:
                        continue
                    name = (job.get("title") or job.get("url") or "")[:40]
                    progress.update(
                        bars[job_id],
                        description=name,
                        completed=job.get("downloaded") or 0,
                        total=job.get("total"),
                    )
                    state = job.get("state")
                    if state in FINISHED_STATES or state == JobState.paused:
                        remaining.discard(job_id)
                        if state == JobState.done:
                            progress.console.print(f"[green]✓[/green] {job.get('rel_path')}")
                        elif state != JobState.paused:
                            failures += 1
                            progress.console.print(f"[red]✗[/red] {name}: {job.get('error')}")
                    if not remaining:
                        break
            except asyncio.CancelledError:
                # Ctrl+C: pause running jobs so the next run resumes from the partial file.
                for job_id in remaining:
                    job_obj = services.store.get(job_id)
                    if job_obj is not None and job_obj.state in ACTIVE_STATES:
                        with contextlib.suppress(Exception):
                            await services.queue.pause(job_id)
                console.print("[yellow]Paused. Run the same command again to resume.[/yellow]")
                raise
    finally:
        await events.aclose()
        await services.stop()
    return 1 if failures else 0


@app.command()
def get(
    urls: Annotated[list[str] | None, typer.Argument(help="Links to download")] = None,
    input_file: Annotated[
        Path | None, typer.Option("--input", "-i", help="Text file with one link per line")
    ] = None,
) -> None:
    """Download one or more links into the downloads folder."""
    all_urls = _read_urls(urls or [], input_file)
    if not all_urls:
        console.print("[red]Give at least one link (or -i list.txt).[/red]")
        raise typer.Exit(code=2)
    try:
        code = asyncio.run(_get(all_urls))
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
    raise typer.Exit(code=code)


async def _probe(url: str) -> None:
    services = Services.build(get_settings())
    try:
        normalized, handler = await services.router.resolve(url)
        result = await handler.probe(normalized)
    finally:
        await services.stop()
    table = Table(show_header=False, box=None)
    table.add_row("Handler", result.handler)
    table.add_row("Title", result.title)
    table.add_row("Size", f"{result.size:,} bytes" if result.size is not None else "unknown")
    for key, value in result.extra.items():
        if value not in (None, {}, ""):
            table.add_row(key.replace("_", " ").capitalize(), str(value))
    console.print(table)


@app.command()
def probe(url: Annotated[str, typer.Argument(help="Link to inspect")]) -> None:
    """Show what is behind a link without downloading it."""
    try:
        asyncio.run(_probe(url))
    except (BlockedURLError, HandlerError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]network error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def jobs(
    limit: Annotated[int, typer.Option(help="How many to show")] = 20,
) -> None:
    """List recent download jobs."""
    services = Services.build(get_settings())
    rows = services.store.list_jobs(limit=limit)
    services.db.dispose()
    if not rows:
        console.print("No jobs yet. Try: anyget get <link>")
        return
    table = Table("State", "Title", "Progress", "Id")
    for job in rows:
        done = f"{job.downloaded:,}" + (f" / {job.total:,}" if job.total else "")
        table.add_row(job.state, (job.title or job.url)[:50], done, job.id[:8])
    console.print(table)


if __name__ == "__main__":
    app()
